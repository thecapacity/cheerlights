import sys
import signal
import time
import board
import neopixel_spi as neopixel
import random
import cheerlights_api
import asyncio
import ast

shutdown_event = asyncio.Event()

TOTAL_LEDS = 165
PIXEL_ORDER = neopixel.GRB
DELAY = .01
BRIGHTNESS = 0.05
BODY_LENGTH = 4
TRAIL_LENGTH = 1 ## use to provide minimum spacing
COLOR_HISOTRY = []

def signal_handler(sig = None, frame = None):
    """Set the shutdown event to signal all tasks to stop."""
    print("\nShutdown signal received. Stopping tasks...")
    asyncio.get_event_loop().call_soon_threadsafe(shutdown_event.set)

def load_color_history(filename = "colors.txt"):
    try:
        with open(filename, 'r') as file:
            content = file.read()
            return ast.literal_eval(content) ## NOTE: this is NOT really secure
    except Exception as e:
        print(f"Error loading color history: {e}")
        return []

def save_color_history(filename = "colors.txt"):
    global COLOR_HISTORY
    try:
        with open(filename, 'w') as file:
            file.write(repr(COLOR_HISTORY))  # Save list as a string representation
    except Exception as e:
        print(f"Error saving color history: {e}")

def wipe_all():
    TOTAL_LEDS = 60 * 4 ## Wipe the full strand even if we can't use all of them

    pixels = neopixel.NeoPixel_SPI(board.SPI(), TOTAL_LEDS, pixel_order=PIXEL_ORDER,
                brightness = 0.5, bpp = 3, auto_write=True)
    pixels.deinit()
    pixels.show()

    return

def adjustBrightness(color, brightness):
    r, g, b = color

    r = int(r * brightness)
    g = int(g * brightness)
    b = int(b * brightness)

    return (r, g, b)

def draw_sprite(pixels, loc, BODY_COLOR):
    loc = loc % TOTAL_LEDS;

    for b in range(0, BODY_LENGTH):    ## Draw Body of Sprite
        index = (loc + b) % TOTAL_LEDS;
        pixels[index] = BODY_COLOR

async def update_color_history():
    global COLOR_HISTORY

    while not shutdown_event.is_set():
        print("Checking Cheerlights")
        hex_code = cheerlights_api.get_current_hex()
        rgb = cheerlights_api.hex_to_rgb(hex_code)

        if len(COLOR_HISTORY) == 0 or rgb != COLOR_HISTORY[-1]:
            COLOR_HISTORY.append(rgb)
            print(f"{len(COLOR_HISTORY)} COLORS: {COLOR_HISTORY}")

        if len(COLOR_HISTORY) * (BODY_LENGTH + TRAIL_LENGTH) > TOTAL_LEDS:
            del COLOR_HISTORY[0]

        await asyncio.sleep(30)

async def main():
    global COLOR_HISTORY

    try:
        pixels = neopixel.NeoPixel_SPI(board.SPI(), TOTAL_LEDS, pixel_order=PIXEL_ORDER,
                brightness = BRIGHTNESS, bpp = 3, auto_write=False)

        # Run the color history updater concurrently
        cheerlights_task = asyncio.create_task(update_color_history())

        POSITION = 0 # Start at 0
        SPEED = 1 # How many 'spaces' (i.e. pixels) to jump each iteration

        while not shutdown_event.is_set():
            pixels.deinit()
            pixels.show()

            NUM_SPRITES = len(COLOR_HISTORY)
            for i, x in enumerate(range(0, TOTAL_LEDS, int(TOTAL_LEDS / NUM_SPRITES+1))):
                draw_sprite(pixels, POSITION + x, COLOR_HISTORY[i])
            pixels.show()

            POSITION = (POSITION + SPEED) % TOTAL_LEDS

            await asyncio.sleep(DELAY)

    finally: # Turn off all LEDs
        print("Cleaning up and exiting...")
        cheerlights_task.cancel()

        pixels.deinit()
        pixels.show()

        save_color_history()

        try:
            await cheerlights_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    global COLOR_HISTORY
    COLOR_HISTORY = load_color_history()

    asyncio.run(main())

    ## wipe_all()
    ## sys.exit(0)

