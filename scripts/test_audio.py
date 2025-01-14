from array import array
from struct import pack
from sys import byteorder
import copy
import pyaudio
import wave
import io

# Imports the Google Cloud client library
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
from google.oauth2 import service_account
import rospy
from std_srvs.srv import Trigger

import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/home/pal/caresses.json"




THRESHOLD = 500  # audio levels not normalised.
CHUNK_SIZE = 1024
RECORD_SECONDS = 15 # about 1sec
FORMAT = pyaudio.paInt16
FRAME_MAX_VALUE = 2 ** 15 - 1
NORMALIZE_MINUS_ONE_dB = 10 ** (-1.0 / 20)
RATE = 16000
CHANNELS = 1
TRIM_APPEND = RATE / 4


def listen_to_mic(req):
    print("Wait in silence to begin recording; wait in silence to terminate")
    record_to_file('test_files/test.wav')
    print("done - result written to test.wav")
    client = speech.SpeechClient()
    credentials = service_account.Credentials.from_service_account_file("/home/pal/caresses.json")
    #client = language.LanguageServiceClient(credentials=credentials)


# The name of the audio file to transcribe
    file_name = 'test_files/test.wav'

# Loads the audio into memory
    with io.open(file_name, 'rb') as audio_file:
        content = audio_file.read()
        audio = types.RecognitionAudio(content=content)

    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code='en-US')

# Detects speech in the audio file
    response = client.recognize(config, audio)

    for result in response.results:
        print('Transcript: {}'.format(result.alternatives[0].transcript))

    req.message = result.alternatives[0].transcript



def is_silent(data_chunk):
    """Returns 'True' if below the 'silent' threshold"""
    return max(data_chunk) < THRESHOLD

def normalize(data_all):
    """Amplify the volume out to max -1dB"""
    # MAXIMUM = 16384
    normalize_factor = (float(NORMALIZE_MINUS_ONE_dB * FRAME_MAX_VALUE)
                        / max(abs(i) for i in data_all))

    r = array('h')
    for i in data_all:
        r.append(int(i * normalize_factor))
    return r

def trim(data_all):
    _from = 0
    _to = len(data_all) - 1
    for i, b in enumerate(data_all):
        if abs(b) > THRESHOLD:
            _from = max(0, i - TRIM_APPEND)
            break
    """
    for i, b in enumerate(reversed(data_all)):
        if abs(b) > THRESHOLD:
            _to = min(len(data_all) - 1, len(data_all) - 1 - i + TRIM_APPEND)
            break
    """
    _to=_from + (RATE * RECORD_SECONDS)-1

    return copy.deepcopy(data_all[_from:(_to + 1)])

def record():
    """Record a word or words from the microphone and 
    return the data as an array of signed shorts."""

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, output=True, frames_per_buffer=CHUNK_SIZE)

    recorded_chunks = 0
    audio_started = False
    data_all = array('h')

    while True:
        # little endian, signed short
        data_chunk = array('h', stream.read(CHUNK_SIZE))
        if byteorder == 'big':
            data_chunk.byteswap()
        data_all.extend(data_chunk)

        #print "recorded_chunks:", recorded_chunks
        #print "len data all:", len(data_all)

        silent = is_silent(data_chunk)

        if audio_started:
                #print "chunk:", recorded_chunks
                recorded_chunks += 1
                if recorded_chunks > int(RATE/CHUNK_SIZE * RECORD_SECONDS):
                    break
                
        elif not silent:
            audio_started = True            

    sample_width = p.get_sample_size(FORMAT)
    stream.stop_stream()
    stream.close()
    p.terminate()

    data_all = trim(data_all)  # we trim before normalize as threshhold applies to un-normalized wave (as well as is_silent() function)

    print "\n len data all trim:", len(data_all)

    data_all = normalize(data_all)
    print "len data all out:", len(data_all)
    return sample_width, data_all

def record_to_file(path):
    "Records from the microphone and outputs the resulting data to 'path'"
    sample_width, data = record()
    data = pack('<' + ('h' * len(data)), *data)

    wave_file = wave.open(path, 'wb')
    wave_file.setnchannels(CHANNELS)
    wave_file.setsampwidth(sample_width)
    wave_file.setframerate(RATE)
    wave_file.writeframes(data)
    wave_file.close()

def add_two_ints_server():
    

if __name__ == '__main__':
    rospy.init_node('add_two_ints_server')
    s = rospy.Service('listen', Trigger, listen_to_mic)
    rospy.spin()
    

