#!/usr/bin/env python3
import math
import serial
import sys
import time
import cv2 # Import OpenCV
import numpy as np # OpenCV uses numpy arrays
import mss # For screen capture

# --- Configuration ---
DEFAULT_GRID_WIDTH = 32
DEFAULT_GRID_HEIGHT = 18
DEFAULT_BAUD_RATE = 115200
DEFAULT_TIMEOUT = 0.2
TARGET_FPS = 5 # Target Frames Per Second to send (as requested)
# Match the start bytes from your C# script (or Arduino)
START_BYTE_1 = 0xA5
START_BYTE_2 = 0x5A

# --- Helper Functions (Pixel Extraction, Input Validation) ---
def prepare_pixel_data_standard_zigzag(frame_rgb, grid_width, grid_height):
    """
    Prepares pixel data in RGB format with standard zigzag pattern.
    Expects frame_rgb to be a NumPy array with shape (grid_height, grid_width, 3).
    """
    h, w, channels = frame_rgb.shape
    # Simple check, resize should handle exact dimensions but good to have
    if h != grid_height or w != grid_width or channels != 3:
        print(f"ERROR: Frame dimensions ({w}x{h}x{channels}) mismatch grid ({grid_width}x{grid_height}x3) in prepare_pixel_data!", file=sys.stderr)
        # Attempt to resize again just in case, though ideally it shouldn't happen here
        try:
            frame_rgb = cv2.resize(frame_rgb, (grid_width, grid_height), interpolation=cv2.INTER_LINEAR)
            print(f"WARN: Resized frame inside prepare_pixel_data due to mismatch.", file=sys.stderr)
            h, w, channels = frame_rgb.shape
            if h != grid_height or w != grid_width or channels != 3: # If still fails
                 return None
        except Exception as e:
            print(f"ERROR: Failed to resize frame during prepare_pixel_data: {e}", file=sys.stderr)
            return None

    pixel_data = []
    for y in range(grid_height):
        if y % 2 == 0: # EVEN row: L -> R
            for x in range(grid_width):
                # frame_rgb is already HxWxRGB
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

# --- Main Script ---
def main():
    print("--- Screen Frame Sender ---")

    # --- Get Inputs ---
    serial_port = input("Enter the serial port name (e.g., COM3, /dev/ttyACM0): ").strip()
    if not serial_port:
        print("ERROR: Serial port cannot be empty.", file=sys.stderr)
        sys.exit(1)

    grid_width = get_int_input("Enter target grid width", DEFAULT_GRID_WIDTH)
    grid_height = get_int_input("Enter target grid height", DEFAULT_GRID_HEIGHT)
    baud_rate = get_int_input("Enter serial baud rate", DEFAULT_BAUD_RATE)
    timeout = get_float_input("Enter serial write timeout in seconds", DEFAULT_TIMEOUT)
    # Target FPS is now fixed
    target_fps = TARGET_FPS
    frame_delay = 1.0 / target_fps

    print(f"\n--- Running Configuration ---")
    print(f"Serial Port: {serial_port}")
    print(f"Baud Rate:   {baud_rate}")
    print(f"Grid Size:   {grid_width}x{grid_height}")
    print(f"Timeout:     {timeout}s")
    print(f"Target FPS:  {target_fps} (Frame Delay: {frame_delay:.4f}s)")
    print(f"---------------------------")

    # --- Setup Screen Capture and Serial ---
    ser = None
    frame_count = 0
    total_start_time = time.monotonic()

    try:
        # 1. Setup Screen Capture (using mss)
        print("Initializing screen capture...")
        sct = mss.mss()
        # Grab the primary monitor (monitor 1)
        # mss monitors[0] is the 'all monitors' virtual screen
        # mss monitors[1] is typically the primary monitor
        if len(sct.monitors) < 2:
            print("ERROR: Could not find primary monitor (only found 'all monitors' screen).", file=sys.stderr)
            sys.exit(1)
        monitor = sct.monitors[1]
        print(f"Capturing from primary monitor: {monitor['width']}x{monitor['height']} at ({monitor['left']}, {monitor['top']})")

        # 2. Open Serial Port
        print(f"Attempting to open serial port {serial_port} at {baud_rate} baud...")
        ser = serial.Serial(serial_port, baud_rate, timeout=1, write_timeout=timeout)
        print(f"Serial port {serial_port} opened successfully.")
        # time.sleep(2.0) # Optional short pause for Arduino/ESP reset

        # --- Main Loop: Capture, Process, Send ---
        print("\nStarting screen capture and sending loop (Ctrl+C to stop)...")

        while True:
            frame_start_time = time.monotonic()

            # --- Capture Screen ---
            # Grab the defined monitor region
            sct_img = sct.grab(monitor)

            # Convert the raw BGRA data from mss to a NumPy array
            # Note: mss grabs BGRA, OpenCV primarily uses BGR
            img_bgra = np.array(sct_img)

            # Convert BGRA to BGR (dropping alpha channel) for OpenCV processing
            frame_bgr = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)

            # --- Process the Frame ---
            # Resize the captured frame to the target grid size
            # Use INTER_LINEAR for speed, INTER_AREA might be better for downscaling but slower
            resized_frame_bgr = cv2.resize(frame_bgr, (grid_width, grid_height), interpolation=cv2.INTER_LINEAR)

            # Convert the resized BGR frame to RGB for sending
            # (Because prepare_pixel_data expects RGB)
            rgb_frame = cv2.cvtColor(resized_frame_bgr, cv2.COLOR_BGR2RGB)

            # Prepare the pixel data in Zigzag format
            pixel_byte_list = prepare_pixel_data_standard_zigzag(rgb_frame, grid_width, grid_height)

            if pixel_byte_list is None:
                 print(f"Skipping frame {frame_count + 1} due to pixel extraction error.")
                 # Ensure timing still works even if skipped
                 # We might need a small sleep to prevent a tight loop on errors
                 time.sleep(0.01) # Small delay
                 continue # Skip sending this frame

            # --- Create Serial Packet ---
            packet_buffer = bytearray([START_BYTE_1, START_BYTE_2])
            packet_buffer.extend(pixel_byte_list)

            expected_packet_length = 2 + (grid_width * grid_height * 3)
            if len(packet_buffer) != expected_packet_length:
                 print(f"WARNING: Frame {frame_count + 1}: Packet length mismatch! Expected {expected_packet_length}, Got {len(packet_buffer)}", file=sys.stderr)
                 # continue # Optional: Skip sending bad packets

            # --- Send Packet ---
            try:
                # Send the packet over serial
                bytes_written = ser.write(packet_buffer)
                # Optional: Flush immediately if needed, but write usually handles it
                # ser.flush()
                frame_count += 1 # Increment count of *sent* frames

            except serial.SerialTimeoutException:
                print(f"\nERROR: Serial write timed out on frame {frame_count + 1}. Check connection/receiver. Aborting.", file=sys.stderr)
                break # Exit the main loop
            except serial.SerialException as e:
                print(f"\nERROR: Serial communication error on frame {frame_count + 1}: {e}. Aborting.", file=sys.stderr)
                break # Exit the main loop
            except Exception as e:
                print(f"\nERROR: Unexpected error during send for frame {frame_count + 1}: {e}. Aborting.", file=sys.stderr)
                break # Exit the main loop

            # --- Frame Rate Control ---
            frame_end_time = time.monotonic()
            processing_time = frame_end_time - frame_start_time

            # Calculate how long to sleep to maintain the target FPS
            sleep_time = frame_delay - processing_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            #else:
            #    # Optional: Print if falling behind schedule
            #    print(f"WARN: Frame {frame_count} processing took too long ({processing_time:.4f}s), falling behind target FPS.", file=sys.stderr)


            # Optional: Print progress occasionally
            if frame_count % (target_fps * 10) == 0: # Print every ~10 seconds
                 print(f"  Sent frame {frame_count}...")


    except KeyboardInterrupt:
        print("\n\nScript interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn unexpected error occurred outside the main loop: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
    finally:
        # --- Cleanup ---
        total_end_time = time.monotonic()
        print("\n--- Cleaning up ---")
        # Close the serial port if it was opened
        if ser and ser.is_open:
            ser.close()
            print(f"Serial port {serial_port} closed.")
        # No video file or cv2 windows to close in this version

        # No downloaded file to delete

        elapsed_time = total_end_time - total_start_time
        print(f"\nSent {frame_count} frames in {elapsed_time:.2f} seconds.")
        if elapsed_time > 0 and frame_count > 0:
             actual_fps = frame_count / elapsed_time
             print(f"Actual average send FPS: {actual_fps:.2f}")
        print("Exiting.")


if __name__ == "__main__":
    main()