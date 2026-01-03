#!/usr/bin/env python3
"""
cbz2xtc - Convert CBZ manga files to XTC format for XTEink X4
All-in-one tool: CBZ extraction → PNG optimization → XTC conversion

Usage:
    cbz2xtc                    # Process current directory
    cbz2xtc /path/to/folder    # Process specific folder
    cbz2xtc --clean            # Process and clean up intermediate files
    cbz2xtc --dither           # Apply dithering for better grayscale→B&W conversion
"""

import os
import sys
import zipfile
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


# Configuration
TARGET_WIDTH = 480
TARGET_HEIGHT = 800

# Global flag for dithering (default True)
USE_DITHERING = True


def find_png2xtc():
    """
    Find png2xtc.py in common locations
    Returns path if found, None otherwise
    """
    possible_paths = [
        # Check environment variable first
        Path(os.environ.get('PNG2XTC_PATH', '')),
        # Same directory as this script
        Path(__file__).parent / "png2xtc.py",
        # epub2xtc subfolder
        Path(__file__).parent / "epub2xtc" / "png2xtc.py",
        # Parent directory
        Path(__file__).parent.parent / "png2xtc.py",
        # Parent epub2xtc folder
        Path(__file__).parent.parent / "epub2xtc" / "png2xtc.py",
        # Windows common location
        Path(r"H:\commandline_tools\epub2xtc\png2xtc.py"),
        # Linux/Mac common locations
        Path.home() / ".local" / "bin" / "png2xtc.py",
        Path("/usr/local/bin/png2xtc.py"),
    ]
    
    for path in possible_paths:
        if path.exists():
            # print("png2xtc exists at ",path) # debugging.
            return path
    
    return None


def optimize_image(img_data, output_path_base, page_num, suffix=""):
    """
    Optimize image for XTEink X4:
    - crop off image margins (if active)
    - Increase image contrast (unless disabled)
    - Split image in half or overlapping thirds horizontally
    - Rotate each half 90° clockwise
    - Resize to fit 480x800 with white padding
    - Convert to grayscale
    - Save as PNG (for XTC conversion)
    """
    try:
        from io import BytesIO
        uncropped_img = Image.open(BytesIO(img_data))

        if suffix == ".1":
            #left half of a spread
            width, height = uncropped_img.size
            uncropped_img = uncropped_img.crop((int(0/100.0*width), int(0/100.0*height), width-int(50/100.0*width), height-int(0/100.0*height)))
        if suffix == ".2":
            #right half of a spread
            width, height = uncropped_img.size
            uncropped_img = uncropped_img.crop((int(50/100.0*width), int(0/100.0*height), width-int(0/100.0*width), height-int(0/100.0*height)))

        if SKIP_ON:
            if str(page_num) in SKIP_PAGES: 
                print("skipping page:",page_num)
                return 0

        if START_PAGE and page_num < START_PAGE:
            # we haven't reached the start page yet
            return 0

        if STOP_PAGE and page_num > STOP_PAGE:
            # we've passed the stop page.
            return 0

        if ONLY_ON:
            if str(page_num) not in ONLY_PAGES: 
                return 0

        if SAMPLE_SET:
            if str(page_num) in SAMPLE_PAGES:
                if uncropped_img.mode != 'L':
                    uncropped_img = uncropped_img.convert('L')
                font = ImageFont.load_default(size=100)
                text_color = 0
                box_color = 255
                print("creating samples for page:",page_num)
                width, height = uncropped_img.size
                text_position = (width//8,height//2)
                # box_position = [(width//8)-10, (height//2)-10, (width//8)+200, (height//2)+40]
                box_position = ((width//8)-30, (height//2), (width//8)+496, (height//2)+120)
                width_proportion = width / 800
                overlapping_third_height = 480 * width_proportion // 1
                shiftdown_to_overlap = overlapping_third_height - (overlapping_third_height * 3 - height) // 2
                contrast_set = 0
                while contrast_set < 9:
                    black_cutoff = 3 * contrast_set
                    white_cutoff = 3 + 9 * contrast_set
                    page_view = ImageOps.autocontrast(uncropped_img, cutoff=(black_cutoff,white_cutoff), preserve_tone=True)
                    draw = ImageDraw.Draw(page_view)
                    draw.rounded_rectangle(box_position, radius=60, fill=box_color, outline=text_color, width=6, corners=(False,True,False,True))
                    draw.text(text_position, f"Contrast {contrast_set}", fill=text_color, font=font)
                    output_page = output_path_base.parent / f"{page_num:04d}_0_contrast{contrast_set}.png"
                    save_with_padding(page_view, output_page, padcolor=PADDING_COLOR)
                    middle_third = page_view.crop((0, shiftdown_to_overlap, width, height - shiftdown_to_overlap))
                    middle_rotated = middle_third.rotate(-90, expand=True)
                    output_middle = output_path_base.parent / f"{page_num:04d}_3_b_contrast{contrast_set}.png"
                    save_with_padding(middle_rotated, output_middle, padcolor=PADDING_COLOR)
                    contrast_set += 1
                crop_set = 0.0
                contrast3img = ImageOps.autocontrast(uncropped_img, cutoff=(9,30), preserve_tone=True)
                while crop_set < 10:
                    allaroundcrop = crop_set
                    page_view = contrast3img.crop((int(allaroundcrop/100.0*width), int(allaroundcrop/100.0*height), width-int(allaroundcrop/100.0*width), height-int(allaroundcrop/100.0*height)))
                    draw = ImageDraw.Draw(page_view)
                    draw.rounded_rectangle(box_position, radius=60, fill=box_color, outline=text_color, width=6, corners=(False,True,False,True))
                    draw.text(text_position, f"Margin {crop_set}", fill=text_color, font=font)
                    output_page = output_path_base.parent / f"{page_num:04d}_9_margin{crop_set}.png"
                    save_with_padding(page_view, output_page, padcolor=30)                    
                    crop_set += 0.5
            else:
                pass
                # print("skipping page:",page_num)
            return 0

        #enhance contrast
        if CONTRAST_BOOST:
            if CONTRAST_VALUE == "0":
                pass  # we don't need to adjust contrast at all.
            elif len(CONTRAST_VALUE.split(',')) > 1:
                #passed a list of 2, first is dark cutoff, second is bright cutoff.
                black_cutoff = 3 * int(CONTRAST_VALUE.split(',')[0])
                white_cutoff = 3 + 9 * int(CONTRAST_VALUE.split(',')[1])
                uncropped_img = ImageOps.autocontrast(uncropped_img, cutoff=(black_cutoff,white_cutoff), preserve_tone=True)
            elif int(CONTRAST_VALUE) < 0 or int(CONTRAST_VALUE) > 8:
                pass # value out of range. we'll treat like 0.
            else:
                black_cutoff = 3 * int(CONTRAST_VALUE)
                white_cutoff = 3 + 9 * int(CONTRAST_VALUE)
                uncropped_img = ImageOps.autocontrast(uncropped_img, cutoff=(black_cutoff,white_cutoff), preserve_tone=True)
        else:
            # nothing set, so we go with the default value of 4. 
            black_cutoff = 3 * 4    # default, contrast level 4 = 12
            white_cutoff = 3 + 9 * 4    # default, contrast level 4 = 39
            uncropped_img = ImageOps.autocontrast(uncropped_img, cutoff=(black_cutoff,white_cutoff), preserve_tone=True)
            # uncropped_img = ImageOps.autocontrast(uncropped_img, cutoff=(8,35), preserve_tone=True)

        # Convert to grayscale
        if uncropped_img.mode != 'L':
            uncropped_img = uncropped_img.convert('L')
        
        img = uncropped_img
        width, height = img.size

        #crop margins in percentage. 
        if MARGIN:
            if MARGIN_VALUE == "0":
                pass #we don't need to do margins at all.
            elif MARGIN_VALUE.lower() == "auto":
                # trim white space from all four sides.
                invert_img=ImageOps.invert(uncropped_img) #invert image
                invert_img=ImageOps.autocontrast(invert_img,cutoff=(59,40))
                image_box_coords = invert_img.getbbox() # bounding rect around anything not true black.
                img = uncropped_img.crop(image_box_coords)
            elif len(MARGIN_VALUE.split(',')) > 1:
                marginlist = MARGIN_VALUE.split(',')
                marginlist.append("0")
                marginlist.append("0") # 2 0s just in case there aren't four values.
                leftcrop = float(marginlist[0])
                topcrop = float(marginlist[1])
                rightcrop = float(marginlist[2])
                bottomcrop = float(marginlist[3])
                img = uncropped_img.crop((int(leftcrop/100.0*width), int(topcrop/100.0*height), width-int(rightcrop/100.0*width), height-int(bottomcrop/100.0*height)))
            else:
                allaroundcrop = float(MARGIN_VALUE);
                img = uncropped_img.crop((int(allaroundcrop/100.0*width), int(allaroundcrop/100.0*height), width-int(allaroundcrop/100.0*width), height-int(allaroundcrop/100.0*height)))

        width, height = img.size
        half_height = height // 2
        total_size = 0

        should_this_split = width < height  #we split most pages that are vertical.
        if str(page_num) in SPLIT_SPREADS_PAGES:
            if suffix == "":  
                # we haven't recursed, this is top level.
                should_this_split = False  #we're not splitting this vertically, we're halving it, then the halves will be split recursively.
            else:
                # we have recursed.
                should_this_split = True  #we can't recurse again, it's been halved, it must be split.
        if SPLIT_ALL:  
            #well, that's easy, we split!
            should_this_split = True
        if suffix == "" and str(page_num) in DONT_SPLIT_PAGES:  
            #also easy, we don't split. Overrides everything. (excepting recursion)
            should_this_split = False

        if should_this_split:
            if INCLUDE_OVERVIEWS or SIDEWAYS_OVERVIEWS or SELECT_OVERVIEWS:
                if SELECT_OVERVIEWS and (str(page_num) not in SELECT_OV_PAGES):
                    pass
                    # we're only doing overviews for some pages, and this one isn't one.
                else:
                    # Process overview page
                    page_view = uncropped_img;
                    if not SIDEWAYS_OVERVIEWS:
                        page_view = uncropped_img.rotate(-90, expand=True)
                    output_page = output_path_base.parent / f"{page_num:04d}{suffix}_0_overview.png"
                    save_with_padding(page_view, output_page, padcolor=PADDING_COLOR)

            if OVERLAP or DESIRED_V_OVERLAP_SEGMENTS or SET_H_OVERLAP_SEGMENTS:
                # DESIRED_V_OVERLAP_SEGMENTS = 3
                # SET_H_OVERLAP_SEGMENTS = 1
                # MINIMUM_V_OVERLAP_PERCENT = 5
                # SET_H_OVERLAP_PERCENT = 75
                # MAX_SPLIT_WIDTH = 80

                number_of_h_segments = SET_H_OVERLAP_SEGMENTS
                total_calculated_width = MAX_SPLIT_WIDTH * number_of_h_segments - int((number_of_h_segments - 1) * (MAX_SPLIT_WIDTH * 0.01 * SET_H_OVERLAP_PERCENT))
                    # so, 1 = 800. 2 with 33% overlap = 1334, 3 with 33% overlap = 1868px, etc.
                established_scale = total_calculated_width * 1.0 / width
                    # so for 2000px wide source, 1= 0.4, 2=0.667, etc. 

                overlapping_width = MAX_SPLIT_WIDTH / established_scale // 1
                shiftover_to_overlap = 0
                if number_of_h_segments > 1:
                    shiftover_to_overlap = overlapping_width - (overlapping_width * number_of_h_segments - width) // (number_of_h_segments - 1)

                number_of_v_segments = DESIRED_V_OVERLAP_SEGMENTS - 1 
                letter_keys = ["a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z"]

                # width_proportion = width / 800
                overlapping_height = 480 / established_scale // 1
                shiftdown_to_overlap = 99999
                while number_of_v_segments < 26 and (shiftdown_to_overlap * 1.0 / overlapping_height) > (1.0 - .01 * MINIMUM_V_OVERLAP_PERCENT):
                    # iterate until we have a number of segments that cover the page with sufficient overlap.
                    # the first iteration should fix the 99999 thing and set up our "base" attempt.
                    number_of_v_segments += 1
                    shiftdown_to_overlap = 0
                    if number_of_v_segments > 1:
                        shiftdown_to_overlap = overlapping_height - (overlapping_height * number_of_v_segments - height) // (number_of_v_segments - 1)

                # # debugging math output
                # print (f"width:{width}, height:{height}")
                # print (f"overlapping_width:{overlapping_width}, overlapping_height:{overlapping_height}")
                # print (f"shiftdown_to_overlap:{shiftdown_to_overlap}, shiftover_to_overlap:{shiftover_to_overlap}")
                # print (f"established_scale:{established_scale}")

                # Make overlapping segments that fill 800x480 screen.
                v = 0
                while v < number_of_v_segments:
                    h = 0
                    while h < number_of_h_segments:
                        segment = img.crop((shiftover_to_overlap*h, shiftdown_to_overlap*v, width-(shiftover_to_overlap*(number_of_h_segments-h-1)), height-(shiftdown_to_overlap*(number_of_v_segments-v-1))))
                        segment_rotated = segment.rotate(-90, expand=True)
                        if number_of_h_segments > 1:
                            output = output_path_base.parent / f"{page_num:04d}{suffix}_3_{letter_keys[v]}_{letter_keys[h]}.png"
                        else:
                            output = output_path_base.parent / f"{page_num:04d}{suffix}_3_{letter_keys[v]}.png"
                        size = save_with_padding(segment_rotated, output, padcolor=PADDING_COLOR)
                        h += 1
                    v += 1


                # # Make overlapping vertical column of full-width segments that fill screen.
                # i = 0
                # while i < number_of_segments:
                #     segment = img.crop((0,shiftdown_to_overlap*i, width, height-(shiftdown_to_overlap*(number_of_segments-i-1))))
                #     segment_rotated = segment.rotate(-90, expand=True)
                #     output = output_path_base.parent / f"{page_num:04d}{suffix}_3_{letter_keys[i]}.png"
                #     size = save_with_padding(segment_rotated, output)
                #     i += 1

                # # Process top third
                # top_third = img.crop((0, 0, width, overlapping_third_height))
                # top_rotated = top_third.rotate(-90, expand=True)
                # output_top = output_path_base.parent / f"{page_num:04d}{suffix}_3_a.png"
                # size = save_with_padding(top_rotated, output_top)
                # total_size += size;

                # # Process middle third
                # middle_third = img.crop((0, shiftdown_to_overlap, width, height - shiftdown_to_overlap))
                # middle_rotated = middle_third.rotate(-90, expand=True)
                # output_middle = output_path_base.parent / f"{page_num:04d}{suffix}_3_b.png"
                # size = save_with_padding(middle_rotated, output_middle)
                # total_size += size;

                # # Process middle third
                # bottom_third = img.crop((0, shiftdown_to_overlap*2, width, height))
                # bottom_rotated = bottom_third.rotate(-90, expand=True)
                # output_bottom = output_path_base.parent / f"{page_num:04d}{suffix}_3_c.png"
                # size = save_with_padding(bottom_rotated, output_bottom)
                # total_size += size;

            else:
                # Process top half
                top_half = img.crop((0, 0, width, half_height))
                top_rotated = top_half.rotate(-90, expand=True)
                output_top = output_path_base.parent / f"{page_num:04d}{suffix}_2_a.png"
                size = save_with_padding(top_rotated, output_top, padcolor=PADDING_COLOR)
                total_size += size
                
                # Process bottom half
                bottom_half = img.crop((0, half_height, width, height))
                bottom_rotated = bottom_half.rotate(-90, expand=True)
                output_bottom = output_path_base.parent / f"{page_num:04d}{suffix}_2_b.png"
                size = save_with_padding(bottom_rotated, output_bottom, padcolor=PADDING_COLOR)
                total_size += size
        
        elif width >= height or str(page_num) in SPLIT_SPREADS_PAGES:
            # Process wide page, or specifically split narrow page (rare, but for two-column layouts)
            # top_half = img.crop((0, 0, width, half_height))
            page_rotated = img.rotate(-90, expand=True)
            output_page = output_path_base.parent / f"{page_num:04d}{suffix}_0_spread.png"
            size = save_with_padding(page_rotated, output_page, padcolor=PADDING_COLOR)
            if SPLIT_SPREADS and (SPLIT_SPREADS_PAGES[0] == "all" or str(page_num) in SPLIT_SPREADS_PAGES):
                splitLeft = optimize_image(img_data, output_path_base, page_num, suffix=suffix+".1")
                splitRight = optimize_image(img_data, output_path_base, page_num, suffix=suffix+".2")
            total_size += size
        else: 
            # This is a dont-split page, treat like overview page
            page_view = uncropped_img;
            if not SIDEWAYS_OVERVIEWS:
                page_view = uncropped_img.rotate(-90, expand=True)
            output_page = output_path_base.parent / f"{page_num:04d}{suffix}_0_overview.png"
            save_with_padding(page_view, output_page, padcolor=PADDING_COLOR)

        return total_size
        
    except Exception as e:
        print(f"    Warning: Could not optimize image: {e}")
        return 0


def save_with_padding(img, output_path, *, padcolor=255):
    """
    Resize image to fit within 480x800 and add white padding
    Optionally apply dithering for better B&W conversion
    """
    img_width, img_height = img.size
    scale = min(TARGET_WIDTH / img_width, TARGET_HEIGHT / img_height)
    
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)
    
    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Apply dithering if enabled (for better grayscale → B&W conversion)
    if USE_DITHERING:
        # Convert to 1-bit with Floyd-Steinberg dithering
        img_resized = img_resized.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        # Convert back to grayscale mode so we can paste on white background
        img_resized = img_resized.convert('L')
    
    # Create background (default padcolor is white)
    result = Image.new('L', (TARGET_WIDTH, TARGET_HEIGHT), color=padcolor)
    
    # Center the image
    x = (TARGET_WIDTH - new_width) // 2
    y = (TARGET_HEIGHT - new_height) // 2
    
    result.paste(img_resized, (x, y))
    result.save(output_path, 'PNG', optimize=True)
    
    return output_path.stat().st_size


def extract_cbz_to_png(cbz_path, temp_dir):
    """
    Extract CBZ and convert to optimized PNGs
    Returns the folder path with PNGs or None if failed
    """
    cbz_name = cbz_path.stem
    output_folder = temp_dir / cbz_name
    output_folder.mkdir(parents=True, exist_ok=True)
    
    try:
        with zipfile.ZipFile(cbz_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
            os_metadata_exclusions = ('__macos') # .cbzs made on Macs sometimes have mac-specific metadata in a __macos directory.
            image_files = [f for f in file_list if f.lower().endswith(image_extensions) and not f.lower().startswith(os_metadata_exclusions)]
            image_files.sort()

            if not image_files:
                print(f"  ✗ No images found in {cbz_name}")
                return None
            
            print(f"  Extracting {len(image_files)} pages...", end=" ", flush=True)
            
            for idx, img_file in enumerate(image_files, 1):
                img_data = zip_ref.read(img_file)
                output_base = output_folder / f"{idx:04d}"
                optimize_image(img_data, output_base, idx)
            
            print(f"✓")
            return output_folder
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return None


def convert_png_folder_to_xtc(png_folder, output_file):
    """
    Convert folder of PNGs to XTC using png2xtc.py
    """
    png2xtc_path = find_png2xtc()
    
    if not png2xtc_path:
        print(f"  ✗ Error: png2xtc.py not found")
        print(f"     Please install epub2xtc or set PNG2XTC_PATH environment variable")
        return False
    
    try:
        # print("trying path:",str(png2xtc_path))
        result = subprocess.run(
            ["python", str(png2xtc_path), str(png_folder), str(output_file)],
            # I had to use the following instead to make this work on my Mac.
            # ["python3", str(png2xtc_path) + "/png2xtc.py", str(png_folder), str(output_file)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0 and output_file.exists():
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"  ✓ Created {output_file.name} ({size_mb:.1f}MB)")
            return True
        else:
            print(f"  ✗ Conversion failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  ✗ Conversion timed out")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def process_cbz_file(cbz_path, output_dir, temp_dir, clean_temp, file_num=None, total_files=None):
    """
    Full pipeline: CBZ → PNG → XTC
    """
    progress_prefix = f"[{file_num}/{total_files}] " if file_num and total_files else ""
    print(f"\n{progress_prefix}Processing: {cbz_path.name}")
    
    start_time = time.time()
    
    # Step 1: Extract and optimize to PNG
    png_folder = extract_cbz_to_png(cbz_path, temp_dir)
    if not png_folder:
        return False, cbz_path.name, 0
    
    # Step 2: Convert to XTC
    output_file = output_dir / f"{cbz_path.stem}.xtc"
    success = convert_png_folder_to_xtc(png_folder, output_file)
    
    # Step 3: Clean up temp files if requested
    if clean_temp and png_folder.exists():
        shutil.rmtree(png_folder)
    
    elapsed = time.time() - start_time
    return success, cbz_path.name, elapsed


def main():
    print("=" * 60)
    print("CBZ to XTC Converter for XTEink X4")
    print("=" * 60)
    
    # Check for help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print("\nConverts CBZ manga files to XTC format optimized for XTEink X4")
        print("\nUsage:")
        print("  cbz2xtc                           # Process current directory")
        print("  cbz2xtc /path/to/folder           # Process specific folder")
        print("  cbz2xtc --no-dither               # Disable dithering")
        print("  cbz2xtc --clean                   # Auto-delete temp PNG files")
        print("  cbz2xtc --no-dither --clean       # Combine options")
        print("\nOptions:")
        print("  --no-dither   Disable Floyd-Steinberg dithering. By default,")
        print("                dithering is ENABLED for better grayscale to")
        print("                black & white conversion. Use this flag for pure")
        print("                threshold conversion (sharper for clean line art).")
        print("\n  --overlap     Split into 3 overlapping screen-filling pieces instead")
        print("                of 2 non-overlapping pieces that may leave margins.")
        print("\n  --split-spreads all or <pagenum> or <pagenum,pagenum,pagenum...>")
        print("                Splits wide pages in half, and then split each of the")
        print("                halves as if they were normal pages. Useful if the")
        print("                wide pages are double-page spreads with text.")
        print("\n  --split-all   Splits ALL pages into pieces, even if those pages")
        print("                are wider than they are tall.")
        print("\n  --skip <pagenum> or <pagenum,pagenum,pagenum...>   skips page")
        print("                or pages entirely.")
        print("\n  --only <pagenum> or <pagenum,pagenum,pagenum...>   only renders")
        print("                the selected page or pages. Tip: If you don't use")
        print("                --clean, this can be used to rerender a problematic")
        print("                page or pages with different settings than the rest.")
        print("\n  --dont-split <pagenum> or <pagenum,pagenum,pagenum...>   don't split")
        print("                page or pages, will use an overview instead (vertical if")
        print("                --sideways-overviews is unset.) For covers and splash pages.")
        print("\n  --contrast-boost <0-8> or <#,#>   Enhances contrast by clipping off,")
        print("                brightest and darkest parts of the image. 0=no boost,")
        print("                4=strong (default), 6=very strong, 8=insane. If you")
        print("                specify two values with a comma, the first will be used")
        print("                for dark parts, and the second for light parts.")
        print("                in general, text will be more readable by increasing")
        print("                dark contrast, and images will gain clarity by")
        print("                increasing light contrast.")
        print("\n  --margin auto or <float> or <left,top,right,bottom>   crops off")
        print("                page margins by a percentage of the width or height.")
        print("                Use a single number to crop from all sides equally, or")
        print("                specify the cropping for each side in LTRB order.")
        print("                '--margin auto' trims white space from all 4 sides.")
        print("                (margin crop is not applied to overview pages.)")
        print("\n  --include-overviews   Show an overview of each page before the")
        print("                split pieces.")
        print("\n  --sideways-overviews   Show a rotated overview of each page before")
        print("                the split pieces. (better quality, but will require)")
        print("                reader to turn their device sideways)")
        print("\n  --select-overviews <pagenum> or <pagenum,pagenum,pagenum...>  Add")
        print("                overview pages for only the specified pages instead of")
        print("                for all pages. Will use vertical overviews if")
        print("                --sideways-overviews is unset. (--dont-split's listed")
        print("                pagenums will still automatically get overviews and")
        print("                don't need to be listed here again.)")
        print("\n  --start <pagenum>   Don't process pages before this page.")
        print("\n  --stop <pagenum>    Don't process pages after this page.")
        print("\n  --pad-black   Pad things that don't fill screen with black instead")
        print("\n  --hsplit-count <#>   Split page horizontally into # segments.")
        print("\n  --hsplit-overlap <float>   horizontal overlap between segments in")
        print("                percent. Default is 70 percent. Lowering this value will")  
        print("                almost always result in automatically splitting the page")  
        print("                vertically into more than 3 segments.")
        print("\n  --hsplit-max-width <#>   limit the width of horizontal segments")
        print("                to less than full screen. (allows for lower amounts of")
        print("                overlap without requiring extra vertical segmentation.)")
        print("\n  --vsplit-target <#>   try to split page vertically into # segments.")
        print("                if this would result it missing data or insufficient")
        print("                overlap of segments, it will automatically add more.")           
        print("\n  --vsplit-min-overlap <float>   minimum vertical overlap between segments.")
        print("                in percent. Default is 5 percent.")  
        print("\n  --sample-set <pagenum> or <pagenum,pagenum,pagenum...>  Build a")
        print("                spread of contrast and margin samples for a page or")
        print("                list of pages. Useful for evaluating what settings")
        print("                you want to use. Does contrasts 0-8, margin 0-10 percent")
        print("\n  --clean       Automatically delete temporary PNG files after")
        print("                conversion. Saves disk space and prevents leftover")
        print("                files from interfering with conversions using different")
        print("                split or overview settings.")
        print("\n  --help, -h    Show this help message")
        print("\nWhat it does:")
        print("  1. Extracts images from CBZ files")
        print("  2. Splits each page in half and rotates 90°")
        print("  3. Resizes to 480×800 with white padding")
        print("  4. Converts to grayscale PNG (with dithering by default)")
        print("  5. Converts PNG to XTC format (fast loading!)")
        print("  6. Uses multithreading (up to 4 parallel conversions)")
        print("\nOutput:")
        print("  - XTC files saved to: ./xtc_output/")
        print("  - Temp PNGs saved to: ./.temp_png/ (unless --clean)")
        print("\nExamples:")
        print("  cbz2xtc                           # Basic conversion (with dithering)")
        print("  cbz2xtc --clean                   # With cleanup")
        print("  cbz2xtc --no-dither               # Without dithering")
        print("  cbz2xtc --contrast 3,5 --margin 5,3.5,5,3.5 --split-spreads all")
        print("                     # good trial settings for a mainstream comic.")
        print("  cbz2xtc --dont-split 1            # show cover as single image")
        print("  cbz2xtc --sideways-overviews --dont-split 17 --select-overviews 19,24")
        print("                     # A sideways overview will be used instead of splits")
        print("                     # for page 17, and a sideways overview will come")
        print("                     # before the splits for pages 19 and 24.")
        print("  cbz2xtc --overlap --hsplit-count 2 --hsplit-overlap 25 --hsplit-max-width 600")
        print("                     # split the page horizontally as well as vertically,")
        print("                     # with a slight overlap, only using 600px screen width on")
        print("                     # target device for the segmented pieces.")
        print("  cbz2xtc D:\\manga --clean          # Specific folder + cleanup")
        return 0
    
    # Parse arguments
    global USE_DITHERING
    global OVERLAP
    global SPLIT_SPREADS
    global SPLIT_SPREADS_PAGES
    global SPLIT_ALL
    global SKIP_ON
    global SKIP_PAGES
    global ONLY_ON
    global ONLY_PAGES
    global DONT_SPLIT
    global DONT_SPLIT_PAGES
    global CONTRAST_BOOST
    global CONTRAST_VALUE
    global MARGIN
    global MARGIN_VALUE
    global INCLUDE_OVERVIEWS
    global SIDEWAYS_OVERVIEWS
    global SELECT_OVERVIEWS
    global SELECT_OV_PAGES
    global START_PAGE
    global STOP_PAGE
    global DESIRED_V_OVERLAP_SEGMENTS
    global SET_H_OVERLAP_SEGMENTS
    global MINIMUM_V_OVERLAP_PERCENT
    global SET_H_OVERLAP_PERCENT
    global MAX_SPLIT_WIDTH
    global SAMPLE_SET
    global SAMPLE_PAGES
    global PADDING_COLOR


    clean_temp = "--clean" in sys.argv
    USE_DITHERING = "--no-dither" not in sys.argv  # Inverted logic
    OVERLAP = "--overlap" in sys.argv
    SPLIT_SPREADS = "--split-spreads" in sys.argv
    SPLIT_ALL = "--split-all" in sys.argv
    SKIP_ON = "--skip" in sys.argv
    ONLY_ON = "--only" in sys.argv
    DONT_SPLIT = "--dont-split" in sys.argv
    CONTRAST_BOOST = "--contrast-boost" in sys.argv
    MARGIN = "--margin" in sys.argv or "--margins" in sys.argv # being nice since easy mistake.
    INCLUDE_OVERVIEWS = "--include-overviews" in sys.argv
    SIDEWAYS_OVERVIEWS = "--sideways-overviews" in sys.argv
    SELECT_OVERVIEWS = "--select-overviews" in sys.argv
    START_PAGE = False
    STOP_PAGE = False
    SAMPLE_SET = "--sample-set" in sys.argv
    SPLIT_SPREADS_PAGES = []
    SKIP_PAGES = []
    ONLY_PAGES = []
    DONT_SPLIT_PAGES = []
    SELECT_OV_PAGES = []
    DESIRED_V_OVERLAP_SEGMENTS = 3
    SET_H_OVERLAP_SEGMENTS = 1
    MINIMUM_V_OVERLAP_PERCENT = 5
    SET_H_OVERLAP_PERCENT = 70
    MAX_SPLIT_WIDTH = 800
    PADDING_COLOR = 255

    if "--pad-black" in sys.argv:
        PADDING_COLOR = 0

    # args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    
    i = 1
    args = []
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--split-spreads":
            SPLIT_SPREADS_PAGES = sys.argv[i+1].split(',')
            print("Will split spread pages:", SPLIT_SPREADS_PAGES)
            # skip the next arg, as it's split spread pages parameter.
            i += 1
        elif arg == "--skip":
            SKIP_PAGES = sys.argv[i+1].split(',')
            print("Will skip pages:", SKIP_PAGES)
            # skip the next arg, as it's skip pages parameter.
            i += 1
        elif arg == "--only":
            ONLY_PAGES = sys.argv[i+1].split(',')
            print("Will only do pages:", ONLY_PAGES)
            i += 1 #skip next arg
        elif arg == "--dont-split":
            DONT_SPLIT_PAGES = sys.argv[i+1].split(',')
            print("Will not split pages:", DONT_SPLIT_PAGES)
            i += 1 #skip next arg
        elif arg == "--contrast-boost":
            CONTRAST_VALUE = sys.argv[i+1]
            print("Contrast setting:", CONTRAST_VALUE)
            i += 1 #skip next arg
        elif arg == "--margin" or arg== "--margins":
            MARGIN_VALUE = sys.argv[i+1]
            print("Margin setting:", MARGIN_VALUE)
            i += 1 #skip next arg
        elif arg == "--select-overviews":
            SELECT_OV_PAGES = sys.argv[i+1].split(',')
            print("Overviews will be added for pages:", SELECT_OV_PAGES)
            i += 1 #skip next arg
        elif arg == "--start":
            START_PAGE = int(sys.argv[i+1])
            print("Generation will start at page:", START_PAGE)
            i += 1 #skip next arg
        elif arg == "--stop":
            STOP_PAGE = int(sys.argv[i+1])
            print("Generation will stop after page:", STOP_PAGE)
            i += 1 #skip next arg
        elif arg == "--vsplit-target":
            OVERLAP = True  # even if not explicitly set.
            DESIRED_V_OVERLAP_SEGMENTS = int(sys.argv[i+1])
            print("will try to verticallly split into ", DESIRED_V_OVERLAP_SEGMENTS, "segments")
            i += 1 #skip next arg
        elif arg == "--vsplit-min-overlap":
            MINIMUM_V_OVERLAP_PERCENT = float(sys.argv[i+1])
            print("Minimum percentage overlap for vertical splits:", MINIMUM_V_OVERLAP_PERCENT)
            i += 1 #skip next arg
        elif arg == "--hsplit-count":
            OVERLAP = True    # even if not explicitly set.
            SET_H_OVERLAP_SEGMENTS = int(sys.argv[i+1])
            print("will horizontally split into ", SET_H_OVERLAP_SEGMENTS, "segments")
            i += 1 #skip next arg
        elif arg == "--hsplit-overlap":
            SET_H_OVERLAP_PERCENT = float(sys.argv[i+1])
            print("will do this percentage overlap for horizontal splits:", SET_H_OVERLAP_PERCENT)
            i += 1 #skip next arg
        elif arg == "--hsplit-max-width":
            MAX_SPLIT_WIDTH = int(sys.argv[i+1])
            print("max width in pixels for horizontal splits:", MAX_SPLIT_WIDTH)
            i += 1 #skip next arg
        elif arg == "--sample-set":
            SAMPLE_PAGES = sys.argv[i+1].split(',')
            print("Sample Mode for pages:", SAMPLE_PAGES)
            i += 1 #skip next arg
        elif arg.startswith("--"):
            pass # do nothing, it's presumably boolean and handled above.
        else:
            args.append(arg) # it's supposed to be a path.
        i += 1

    # Get input directory
    if args:
        input_dir = Path(args[0])
    else:
        input_dir = Path.cwd()
    
    if not input_dir.exists():
        print(f"Error: Directory '{input_dir}' does not exist")
        return 1
    
    print(f"\nInput directory: {input_dir.absolute()}")
    if USE_DITHERING:
        print("Dithering: ENABLED (better for screentones/gradients)")
    else:
        print("Dithering: DISABLED (use --dither to enable)")
    
    # Determine number of threads
    max_workers = min(4, os.cpu_count() or 1)  # Use up to 4 threads
    print(f"Threads: {max_workers} (parallel processing)")
    
    # Create output and temp directories
    output_dir = input_dir / "xtc_output"
    temp_dir = input_dir / ".temp_png"
    
    output_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)
    
    # Find all CBZ files (including in subdirectories)
    cbz_files = []
    
    # Check current directory
    cbz_files.extend(sorted(input_dir.glob("*.cbz")))
    cbz_files.extend(sorted(input_dir.glob("*.CBZ")))
    
    # Only check subdirectories if no CBZ files found in current directory
    if not cbz_files:
        for subdir in input_dir.iterdir():
            if subdir.is_dir() and subdir.name not in ["xtc_output", ".temp_png"]:
                cbz_files.extend(sorted(subdir.glob("*.cbz")))
                cbz_files.extend(sorted(subdir.glob("*.CBZ")))
    
    # Remove any duplicates (shouldn't happen now, but just in case)
    cbz_files = list(dict.fromkeys(cbz_files))
    
    if not cbz_files:
        print(f"\nNo CBZ files found in '{input_dir}' or its subdirectories")
        return 1
    
    print(f"\nFound {len(cbz_files)} CBZ file(s)")
    print(f"Output directory: {output_dir.absolute()}")
    print(f"Temp directory: {temp_dir.absolute()}")
    if clean_temp:
        print("Clean mode: Temporary files will be deleted after conversion")
    print("-" * 60)
    
    # Verify png2xtc.py exists
    png2xtc_path = find_png2xtc()
    if not png2xtc_path:
        print(f"\n✗ Error: png2xtc.py not found")
        print(f"\nThe epub2xtc library is required to convert PNG to XTC format.")
        print(f"Repository: https://github.com/jonasdiemer/epub2xtc")
        
        # Ask user if they want to clone it
        try:
            response = input("\nWould you like to clone epub2xtc now? (Y/n): ").strip().lower()
            
            if response in ['y', 'yes', '']:
                # Determine where to clone
                clone_dir = Path(__file__).parent / "epub2xtc"
                
                print(f"\nCloning to: {clone_dir}")
                print("Running: git clone https://github.com/jonasdiemer/epub2xtc.git")
                
                result = subprocess.run(
                    ["git", "clone", "https://github.com/jonasdiemer/epub2xtc.git", str(clone_dir)],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("✓ Successfully cloned epub2xtc!")
                    print("\nPlease run cbz2xtc again.")
                    return 0
                else:
                    print(f"✗ Failed to clone: {result.stderr}")
                    print("\nPlease clone manually:")
                    print("  git clone https://github.com/jonasdiemer/epub2xtc.git")
                    return 1
            else:
                print("\nPlease install epub2xtc manually:")
                print("  git clone https://github.com/jonasdiemer/epub2xtc.git")
                print("\nOr set PNG2XTC_PATH environment variable to the location of png2xtc.py")
                return 1
                
        except KeyboardInterrupt:
            print("\n\nCancelled by user.")
            return 1
        except Exception as e:
            print(f"\nError: {e}")
            print("\nPlease install epub2xtc manually:")
            print("  git clone https://github.com/jonasdiemer/epub2xtc.git")
            return 1
    
    print(f"Using png2xtc.py from: {png2xtc_path.parent}")
    
    # Process files with multithreading
    start_time = time.time()
    success_count = 0
    total_time = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_cbz = {
            executor.submit(process_cbz_file, cbz_file, output_dir, temp_dir, clean_temp, idx, len(cbz_files)): cbz_file
            for idx, cbz_file in enumerate(cbz_files, 1)
        }
        
        # Process results as they complete
        for future in as_completed(future_to_cbz):
            success, filename, elapsed = future.result()
            if success:
                success_count += 1
                total_time += elapsed
                avg_time = total_time / success_count
                remaining = (len(cbz_files) - success_count) * avg_time
                print(f"  ⏱  {elapsed:.1f}s | Est. remaining: {remaining/60:.1f}min")
    
    elapsed_total = time.time() - start_time
    
    print("-" * 60)
    print(f"\nCompleted! Successfully converted {success_count}/{len(cbz_files)} files")
    print(f"Total time: {elapsed_total/60:.1f} minutes")
    print(f"Average: {elapsed_total/len(cbz_files):.1f}s per file")
    print(f"\nXTC files are in: {output_dir.absolute()}")
    
    # Clean up temp directory if empty or if clean mode
    if clean_temp:
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                print("Temporary files cleaned up")
        except:
            pass
    else:
        print(f"Temporary PNG files are in: {temp_dir.absolute()}")
        print("(Run with --clean flag to auto-delete temp files)")
    
    print("\nTransfer the .xtc files to your XTEink X4!")
    
    return 0 if success_count == len(cbz_files) else 1


if __name__ == "__main__":
    sys.exit(main())