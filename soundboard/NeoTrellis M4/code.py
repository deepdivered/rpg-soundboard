# SPDX-FileCopyrightText: 2018 Limor Fried for Adafruit Industries
# SPDX-License-Identifier: MIT
# Enhanced by Israel Perez

import time
import board
import audioio
#  import audiocore
import audiomixer
import adafruit_fancyled.adafruit_fancyled as fancy
import adafruit_trellism4
#  import digitalio
import audiomp3 

from color_names import *  # pylint: disable=wildcard-import,unused-wildcard-import


PLAY_SAMPLES_ON_START = False
SELECTED_COLOR = WHITE
SAMPLE_FOLDER = "/samples/"  # the name of the folder containing the samples
SAMPLES = []


# For the intro, pick any number of colors to make a fancy gradient!
INTRO_SWIRL = [RED, GREEN, BLUE]

# Our keypad + neopixel driver
trellis = adafruit_trellism4.TrellisM4Express(rotation=0)


# load the sound & color specifications
with open("soundboard.txt", "r") as f:
    for line in f:
        cleaned = line.strip()
        if len(cleaned) > 0 and cleaned[0] != "#":
            if cleaned == "pass":
                SAMPLES.append(("does_not_exist.mp3", BLACK))
            else:
                f_name, color = cleaned.split(",", 1)
                SAMPLES.append((f_name.strip(), eval(color.strip())))

# set led brightness
trellis.pixels.brightness = 0.1   
           
# Play the welcome mp3 (if its there) and run intro sequence
# with audioio.AudioOut(board.A1) as audio: # mono
with audioio.AudioOut(board.A1, right_channel=board.A0) as audio:  # stereo
    try:
        f = open("welcome.mp3", "rb")
        mp = audiomp3.MP3Decoder(f)
        audio.play(mp)
        swirl = 0  # we'll swirl through the colors in the gradient
        while audio.playing:
            for i in range(32):
                palette_index = ((swirl+i) % 32) / 32
                color = fancy.palette_lookup(INTRO_SWIRL, palette_index)
                # print(palette_index, fancy.denormalize(color)) display RGB of swirl
                trellis.pixels[(i % 8, i//8)] = color.pack()
            swirl += 1
            time.sleep(0.005)
        f.close()
        # Clear all pixels
        trellis.pixels.fill(0)
        # just hold a moment
        time.sleep(0.5)
    except OSError:
        # no welcome.mp3 file 
        pass

# Parse the first file to figure out what format its in
channel_count = None
bits_per_sample = None
sample_rate = None
with open(SAMPLE_FOLDER+SAMPLES[0][0], "rb") as f:
    mp3 = audiomp3.MP3Decoder(f)
    channel_count = mp3.channel_count
    bits_per_sample = mp3.bits_per_sample
    sample_rate = mp3.sample_rate
    print("%d channels, %d bits per sample, %d Hz sample rate " %
          (mp3.channel_count, mp3.bits_per_sample, mp3.sample_rate))
    
    # Audio playback object - we'll go with either mono or stereo depending on
    # what we see in the first file
    if mp3.channel_count == 1:
        audio = audioio.AudioOut(board.A1)
    elif mp3.channel_count == 2:
        audio = audioio.AudioOut(board.A1, right_channel=board.A0)
    else:
        raise RuntimeError("Must be mono or stereo mp3s!")

mixer = audiomixer.Mixer(voice_count=2, 
        sample_rate=sample_rate, 
        channel_count=channel_count, 
        bits_per_sample=bits_per_sample, 
        samples_signed=True)
audio.play(mixer)

# Clear all pixels
trellis.pixels.fill(0)

# Light up button with a valid sound file attached
for i, v in enumerate(SAMPLES):
    filename = SAMPLE_FOLDER+v[0]
    try:
        with open(filename, "rb") as f:
            mp3 = audiomp3.MP3Decoder(f)
            print(filename,
                  "%d channels, %d bits per sample, %d Hz sample rate " %
                  (mp3.channel_count, mp3.bits_per_sample, mp3.sample_rate))
            if mp3.channel_count is not channel_count:
                pass
            if mp3.bits_per_sample is not bits_per_sample:
                pass
            if mp3.sample_rate is not sample_rate:
                pass
            trellis.pixels[(i % 8, i//8)] = v[1]
            if PLAY_SAMPLES_ON_START:
                audio.play(mp3)
                while audio.playing:
                    pass
    except OSError:
        # File not found! skip to next
        if filename is not SAMPLE_FOLDER+"does_not_exist.mp3":
            print('Not found: ' + filename)
        pass

def stop_playing_sample(playback_details):
    print("playing: ", playback_details)
    mixer.stop_voice(playback_details["voice"])
    trellis.pixels[playback_details["neopixel_location"]] = playback_details["\
    neopixel_color"]
    playback_details["file"].close()
    playback_details["voice"] = None
    playback_details["sample_num"] = None

current_press = set()
current_background = {"voice" : None, "sample_num": None}
currently_playing = {"voice" : None}
# last_samplenum = None
while True:
    pressed = set(trellis.pressed_keys)
    just_pressed = pressed - current_press

    for down in just_pressed:
        sample_num = down[1]*8 + down[0]
        try:
            filename = SAMPLE_FOLDER+SAMPLES[sample_num][0]
            f = open(filename, "rb")
            mp3 = audiomp3.MP3Decoder(f)
            print(sample_num, filename)
            # Check to see if its background music 
            if filename[9:13] == "bgm_":
                # Check if sample is already playing then stop it
                if current_background["sample_num"] == sample_num: 
                    stop_playing_sample(current_background)
                    break
                # Check to see if it needs to loop
                will_loop = False
                file_name = filename.split(".")[0]
                if file_name[len(file_name) - 4:] == "loop":
                    will_loop = True
                if current_background["voice"] is not None:
                    print("Interrupt")
                    stop_playing_sample(current_background)
                trellis.pixels[down] = WHITE
                mixer.play(mp3, voice=0, loop=will_loop)
                current_background = {
                    "voice": 0,
                    "neopixel_location": down,
                    "neopixel_color": SAMPLES[sample_num][1],
                    "sample_num": sample_num,
                    "file": f}
            else:
                if currently_playing["voice"] is not None:
                    print("Interrupt")
                    stop_playing_sample(currently_playing)
                trellis.pixels[down] = WHITE
                mixer.play(mp3, voice=1, loop=False)
                currently_playing = {
                    "voice": 1,
                    "neopixel_location": down,
                    "neopixel_color": SAMPLES[sample_num][1],
                    "sample_num": sample_num,
                    "file": f}
        except OSError:
            pass  # File not found! skip to next

    # check if any samples are done
    if not mixer.playing:
        if currently_playing["voice"] is not None:
            stop_playing_sample(currently_playing)
        if current_background["voice"] is not None:
            stop_playing_sample(current_background)

    time.sleep(0.01)  # a little delay here helps avoid debounce annoyances
    current_press = pressed
