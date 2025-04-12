#!/usr/bin/env python3
import math
import serial
import sys
import time
import cv2 # Import OpenCV
import numpy as np # OpenCV usa numpy arrays
import subprocess # Para executar yt-dlp
import os # Para manipulação de arquivos (remoção)
import platform # Para verificar o OS (opcional, para encoding)
# from cv2 import VideoCapture # Não precisa mais importar explicitamente

# --- Configuration ---
DEFAULT_GRID_WIDTH = 32
DEFAULT_GRID_HEIGHT = 18
DEFAULT_BAUD_RATE = 115200
DEFAULT_TIMEOUT = 0.2
DEFAULT_TARGET_FPS = 5 # Target Frames Per Second to send (Adjust as needed)
# O FPS original será lido do arquivo baixado, mas limitaremos o envio a target_fps
# Match the start bytes from your C# script
START_BYTE_1 = 0xA5
START_BYTE_2 = 0x5A
# yt-dlp format selection (prioritize mp4 for compatibility)
# Choose a resolution reasonable for download size and processing
YTDLP_FORMAT = "bestvideo[ext=mp4][height<=480]/bestvideo[height<=480]/bestvideo"
DOWNLOAD_FILENAME = "temp_youtube_video" # Base name for downloaded file (extension added by yt-dlp)
DOWNLOAD_TIMEOUT_SECONDS = 300 # Timeout for the download process (e.g., 5 minutes)


# --- Helper Functions (Pixel Extraction, Input Validation) ---
# (Keep prepare_pixel_data_standard_zigzag, get_int_input, get_float_input exactly as before)
def prepare_pixel_data_standard_zigzag(frame_rgb, grid_width, grid_height):
    h, w, channels = frame_rgb.shape
    if h != grid_height or w != grid_width or channels != 3:
        print(f"ERROR: Frame dimensions ({w}x{h}x{channels}) mismatch grid ({grid_width}x{grid_height}x3) in prepare_pixel_data!", file=sys.stderr)
        return None
    pixel_data = []
    for y in range(grid_height):
        if y % 2 == 0: # EVEN row: L -> R
            for x in range(grid_width):
                r, g, b = frame_rgb[y, x]
                pixel_data.extend([r, g, b])
        else: # ODD row: R -> L
            for x in range(grid_width - 1, -1, -1):
                r, g, b = frame_rgb[y, x]
                pixel_data.extend([r, g, b])
    return pixel_data

def get_int_input(prompt, default_value):
    while True:
        value_str = input(f"{prompt} (default: {default_value}): ").strip()
        if not value_str: return default_value
        try:
            value = int(value_str)
            if value > 0: return value
            else: print("Please enter a positive integer.")
        except ValueError: print("Invalid input. Please enter an integer.")

def get_float_input(prompt, default_value):
     while True:
        value_str = input(f"{prompt} (default: {default_value}): ").strip()
        if not value_str: return default_value
        try:
            value = float(value_str)
            if value > 0: return value
            else: print("Please enter a positive number.")
        except ValueError: print("Invalid input. Please enter a number.")

# --- Function to DOWNLOAD YouTube video ---
def download_youtube_video(youtube_url, format_select=YTDLP_FORMAT, output_filename=DOWNLOAD_FILENAME, timeout=DOWNLOAD_TIMEOUT_SECONDS):
    """
    Uses yt-dlp to DOWNLOAD a YouTube video to a local file.
    Returns the full path to the downloaded file on success, None otherwise.
    """
    # Create the output template - yt-dlp will add the correct extension
    output_template = f"{output_filename}.%(ext)s"

    print(f"\nAttempting to download video: {youtube_url}")
    print(f"Using format selection: {format_select}")
    print(f"Saving to file pattern: {output_template}")
    print(f"Download timeout set to: {timeout} seconds")

    downloaded_filepath = None # Variable to store the actual final filename

    try:
        # Command: yt-dlp -f <format> -o <output_template> <youtube_url>
        command = ['yt-dlp', '-f', format_select, '-o', output_template, youtube_url]

        print("Starting download process...")
        # Run the command, allow output to be seen, set timeout
        process = subprocess.run(command, text=True, check=True, encoding='utf-8', timeout=timeout)

        # Unfortunately, yt-dlp doesn't easily return the *exact* filename it used via stdout when downloading.
        # We need to figure it out. We can list files matching the pattern.
        # This is a bit fragile but often works.
        possible_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv'] # Add more if needed
        for ext in possible_extensions:
            potential_file = f"{output_filename}{ext}"
            if os.path.exists(potential_file):
                downloaded_filepath = potential_file
                print(f"Download complete. Video saved as: {downloaded_filepath}")
                break

        if not downloaded_filepath:
             # Fallback: Try getting the filename directly if yt-dlp has an option (newer versions might)
             # Or, more robustly, use yt-dlp --print filename -o template url
             try:
                 get_name_command = ['yt-dlp', '--print', 'filename', '-f', format_select, '-o', output_template, youtube_url]
                 name_process = subprocess.run(get_name_command, capture_output=True, text=True, check=True, encoding='utf-8', timeout=30)
                 potential_file = name_process.stdout.strip()
                 if os.path.exists(potential_file):
                     downloaded_filepath = potential_file
                     print(f"Download complete. Video saved as: {downloaded_filepath} (using --print filename)")
                 else:
                     print(f"ERROR: yt-dlp reported filename '{potential_file}' but it doesn't exist.", file=sys.stderr)
                     return None
             except Exception as name_e:
                 print(f"ERROR: Could not determine exact downloaded filename automatically after download completed successfully according to yt-dlp.", file=sys.stderr)
                 print(f"Attempted pattern: {output_template}. Please check manually.", file=sys.stderr)
                 print(f"Error during filename check: {name_e}", file=sys.stderr)
                 return None


        return downloaded_filepath

    except FileNotFoundError:
        print("ERROR: 'yt-dlp' command not found. Is yt-dlp installed and in your PATH?", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"ERROR: yt-dlp download timed out after {timeout} seconds.", file=sys.stderr)
        # Clean up potentially partial file
        print("Attempting to clean up potentially partial download...")
        possible_extensions = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.part']
        for ext in possible_extensions:
            potential_file = f"{output_filename}{ext}"
            if os.path.exists(potential_file):
                try:
                    os.remove(potential_file)
                    print(f"Removed partial file: {potential_file}")
                except OSError as e:
                    print(f"Warning: Could not remove partial file {potential_file}: {e}", file=sys.stderr)
        return None
    except subprocess.CalledProcessError as e:
        print(f"ERROR: yt-dlp failed with error code {e.returncode}.", file=sys.stderr)
        # stderr might be captured if capture_output=True, but we didn't use it here
        # print(f"yt-dlp stderr:\n{e.stderr}", file=sys.stderr) # Uncomment if needed
        print("Check the YouTube URL, video availability, format selection, and your internet connection.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while running yt-dlp: {e}", file=sys.stderr)
        return None

# --- Main Script ---
def main():
    print("--- YouTube Video Frame Sender (Download Mode) ---")

    # --- Get Inputs ---
    youtube_url = input("Enter the YouTube video URL: ").strip()
    if not youtube_url:
        print("ERROR: YouTube URL cannot be empty.", file=sys.stderr)
        sys.exit(1)

    serial_port = input("Enter the serial port name (e.g., COM3, /dev/ttyACM0): ").strip()
    if not serial_port:
        print("ERROR: Serial port cannot be empty.", file=sys.stderr)
        sys.exit(1)

    grid_width = get_int_input("Enter target grid width", DEFAULT_GRID_WIDTH)
    grid_height = get_int_input("Enter target grid height", DEFAULT_GRID_HEIGHT)
    baud_rate = get_int_input("Enter serial baud rate", DEFAULT_BAUD_RATE)
    timeout = get_float_input("Enter serial write timeout in seconds", DEFAULT_TIMEOUT)
    target_fps = get_int_input("Enter target FPS to send", DEFAULT_TARGET_FPS)

    frame_delay = 1.0 / target_fps

    print(f"\n--- Running Configuration ---")
    print(f"YouTube URL: {youtube_url}")
    print(f"Serial Port: {serial_port}")
    print(f"Baud Rate:   {baud_rate}")
    print(f"Grid Size:   {grid_width}x{grid_height}")
    print(f"Timeout:     {timeout}s")
    print(f"Target FPS:  {target_fps} (Frame Delay: {frame_delay:.4f}s)")
    print(f"Download File: {DOWNLOAD_FILENAME}.*")
    print(f"---------------------------")

    # --- Download Video ---
    video_filepath = download_youtube_video(youtube_url)
    if not video_filepath:
        print("Exiting due to download failure.")
        sys.exit(1)

    # --- Setup Video Capture (from local file) and Serial ---
    cap = None
    ser = None
    frame_count = 0
    total_start_time = time.monotonic()


    try:
        # 1. Open Video File
        print(f"\nOpening downloaded video file: {video_filepath}")
        cap = cv2.VideoCapture(video_filepath)
        if not cap.isOpened():
            print(f"ERROR: OpenCV could not open the downloaded video file: {video_filepath}", file=sys.stderr)
            # Attempt cleanup before exiting
            if os.path.exists(video_filepath):
                try:
                    os.remove(video_filepath)
                    print(f"Cleaned up downloaded file: {video_filepath}")
                except OSError as e:
                    print(f"Warning: Could not clean up file {video_filepath}: {e}", file=sys.stderr)
            sys.exit(1)

        # Get video properties from the file
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        original_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Video file opened. Info: {original_width}x{original_height} @ {original_fps:.2f} FPS, {original_frames} frames")
        if original_fps <= 0:
            print("Warning: Could not read valid FPS from video file. Frame skipping might be inaccurate.", file=sys.stderr)
            frames_to_skip = 1 # Default to reading every frame if FPS is unknown
        else:
            # Calculate frames to skip based on original FPS and target sending FPS
            frames_to_skip = max(1, round(original_fps / target_fps)) # Read at least 1 frame
        print(f"Target send FPS is {target_fps}. Reading approx. 1 frame for every {frames_to_skip} frames in the video.")


        # 2. Open Serial Port
        print(f"Attempting to open serial port {serial_port} at {baud_rate} baud...")
        ser = serial.Serial(serial_port, baud_rate, timeout=1, write_timeout=timeout)
        print(f"Serial port {serial_port} opened successfully.")
        # time.sleep(2.0) # Optional short pause

        # --- Main Loop: Read, Process, Send ---
        print("\nStarting frame processing and sending loop (Ctrl+C to stop)...")
        processed_frame_index = 0 # Track which frame we are processing from the source
        last_frame_send_time = time.monotonic() # Initialize timing

        while True:
            frame_start_time = time.monotonic()

            # --- Read Frame (with skipping) ---
            ret = False
            frame = None
            for _ in range(frames_to_skip):
                 ret, frame = cap.read()
                 processed_frame_index += 1
                 if not ret: # If reading fails at any point (incl. end of file), break the skip loop
                     break

            if not ret:
                print(f"\nEnd of video file reached after processing frame {processed_frame_index -1}.")
                break # Exit the main loop

            # --- Process the Frame ---
            resized_frame = cv2.resize(frame, (grid_width, grid_height), interpolation=cv2.INTER_LINEAR)
            rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            pixel_byte_list = prepare_pixel_data_standard_zigzag(rgb_frame, grid_width, grid_height)

            if pixel_byte_list is None:
                 print(f"Skipping source frame index {processed_frame_index -1} due to pixel extraction error.")
                 # Adjust timing correctly even if skipped
                 last_frame_send_time = time.monotonic() # Reset timer to avoid rush on next frame
                 continue

            packet_buffer = bytearray([START_BYTE_1, START_BYTE_2])
            packet_buffer.extend(pixel_byte_list)

            expected_packet_length = 2 + (grid_width * grid_height * 3)
            if len(packet_buffer) != expected_packet_length:
                 print(f"WARNING: Frame {frame_count + 1} (Source idx {processed_frame_index -1}): Packet length mismatch! Expected {expected_packet_length}, Got {len(packet_buffer)}", file=sys.stderr)
                 # continue # Optional: Skip sending bad packets

            # --- Send Packet ---
            try:
                bytes_written = ser.write(packet_buffer)
                frame_count += 1 # Increment count of *sent* frames

            except serial.SerialTimeoutException:
                print(f"\nERROR: Serial write timed out on frame {frame_count + 1}. Aborting.", file=sys.stderr)
                break
            except serial.SerialException as e:
                print(f"nERROR: Serial communication error on frame {frame_count + 1}: {e}. Aborting.", file=sys.stderr)
                break
            except Exception as e:
                print(f"\nERROR: Unexpected error during send for frame {frame_count + 1}: {e}. Aborting.", file=sys.stderr)
                break

            # --- Frame Rate Control ---
            frame_end_time = time.monotonic()
            processing_time = frame_end_time - frame_start_time
            # Calculate sleep needed based on *target* delay, accounting for processing time
            sleep_time = frame_delay - processing_time
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Optional: Print progress more aligned with video progress
            if frame_count % (target_fps * 10) == 0 and original_frames > 0: # Print every ~10s of sent frames
                 progress_percent = (processed_frame_index / original_frames) * 100
                 print(f"  Sent frame {frame_count}... (Video progress: ~{progress_percent:.1f}%)")
            elif frame_count % (target_fps * 10) == 0:
                 print(f"  Sent frame {frame_count}...")


    except KeyboardInterrupt:
        print("\n\nScript interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred outside the main loop: {e}", file=sys.stderr)
    finally:
        # --- Cleanup ---
        total_end_time = time.monotonic()
        print("\n--- Cleaning up ---")
        if cap and cap.isOpened():
            cap.release()
            print("Video file capture released.")
            cv2.destroyAllWindows()
        if ser and ser.is_open:
            ser.close()
            print(f"Serial port {serial_port} closed.")

        # Delete the downloaded video file
        if video_filepath and os.path.exists(video_filepath):
            try:
                os.remove(video_filepath)
                print(f"Successfully deleted downloaded file: {video_filepath}")
            except OSError as e:
                print(f"ERROR: Could not delete downloaded file {video_filepath}: {e}", file=sys.stderr)
        elif video_filepath:
             print(f"Info: Downloaded file path was '{video_filepath}' but it wasn't found for cleanup.")


        elapsed_time = total_end_time - total_start_time
        print(f"\nSent {frame_count} frames in {elapsed_time:.2f} seconds.")
        if elapsed_time > 0 and frame_count > 0:
             actual_fps = frame_count / elapsed_time
             print(f"Actual average send FPS: {actual_fps:.2f}")
        print("Exiting.")


if __name__ == "__main__":
    main()