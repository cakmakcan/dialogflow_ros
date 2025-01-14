#!/usr/bin/env python

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio
import Queue
import rospy
import time
from std_msgs.msg import String
from dialogflow_ros import DialogflowClient
from dialogflow_ros.msg import *


class GspeechClient(object):
    def __init__(self):
	#wrong_ans = ["You have missed an item or put the wrong item. Please correct the order!", \
	#	"I didn't get that. Can you say it again?", \
#		"I missed what you said. What was that?", \
#		"Sorry, could you say that again?", \
#"Sorry, can you say that again?", \
#"Can you say that again?", \
#"Sorry, I didn't get that. Can you rephrase?", \
#"Sorry, what was that?", \
#"One more time?", \
	self.repeat_intent = ['EOC']

        # Audio stream input setup
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        self.CHUNK = 4096
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                      rate=RATE, input=True,
                                      frames_per_buffer=self.CHUNK,
                                      stream_callback=self._get_data)
        self._buff = Queue.Queue()  # Buffer to hold audio data
        self.closed = False

        # ROS Text Publisher
        text_topic = rospy.get_param('/text_topic', '/dialogflow_text')
        self.text_pub = rospy.Publisher(text_topic, String, queue_size=10)

    def _get_data(self, in_data, frame_count, time_info, status):
        """Daemon thread to continuously get audio data from the server and put
         it in a buffer.
        """
        # Uncomment this if you want to hear the audio being replayed.
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def _generator(self):
        """Generator function that continuously yields audio chunks from the buffer.
        Used to stream data to the Google Speech API Asynchronously.
        """
        while not self.closed:
            # Check first chunk of data
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Read in a stream till the end using a non-blocking get()
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except Queue.Empty:
                    break

            yield b''.join(data)

    def _listen_print_loop(self, responses, dc):
        """Iterates through server responses and prints them.
        The responses passed is a generator that will block until a response
        is provided by the server.
        Each response may contain multiple results, and each result may contain
        multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
        print only the transcription for the top alternative of the top result.
        """
	for response in responses:
		
		# If not a valid response, move on to next potential one
		if not response.results:
				continue
		print("I heard: %s" % response)		
		# The `results` list is consecutive. For streaming, we only care about
		# the first result being considered, since once it's `is_final`, it
		# moves on to considering the next utterance.
		result = response.results[0]
		if not result.alternatives:
			continue
	
		
		# Display the transcription of the top alternative.
		transcript = result.alternatives[0].transcript

		# Parse the final utterance
		if result.is_final:
			rospy.loginfo("Google Speech result: {}".format(result))
			# Received data is Unicode, convert it to string
			transcript = transcript.encode('utf-8')
			# Strip the initial space, if any
			if transcript.startswith(' '):
				transcript = transcript[1:]
		    
                    # Exit if needed
			if transcript.lower() == 'exit':
				self.shutdown()
                # Send the rest of the sentence to topic
			self.text_pub.publish(transcript)
		
  		dr = DialogflowRequest(query_text=transcript)
		resp_tmp = dc.detect_intent_text(dr)
		resp = resp_tmp.fulfillment_text
		intent = resp_tmp.intent
		self.text_pub.publish(resp)	
		return intent not in self.repeat_intent

		

    def gspeech_client(self):
        """Creates the Google Speech API client, configures it, and sends/gets
        audio/text data for parsing.
        """
        language_code = 'en-US'
        client = speech.SpeechClient()
        config = types.RecognitionConfig(
			encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
			sample_rate_hertz=44100,
			language_code=language_code)
        streaming_config = types.StreamingRecognitionConfig(
			config=config,
			interim_results=True)
	dc = DialogflowClient()
	repeat = True
	while repeat and not rospy.is_shutdown():
		print("listening for msg")
  	    # Hack from Google Speech Python docs, very pythonic c:
		requests = (types.StreamingRecognizeRequest(audio_content=content) for content in self._generator())
		responses = client.streaming_recognize(streaming_config, requests)
		print("Message taken")
		repeat = self._listen_print_loop(responses, dc)
		#dc = DialogflowClient()
		#dr = DialogflowRequest(query_text=transcript)
		#resp1 = dc.detect_intent_text(dr)

    def shutdown(self):
        """Shut down as cleanly as possible"""
        rospy.loginfo("Shutting down")
        self.closed = True
        self._buff.put(None)
        self.stream.close()
        self.audio.terminate()
        exit()

    def start_client(self):
        """Entry function to start the client"""
        try:
            rospy.loginfo("Starting Google speech mic client")
            self.gspeech_client()
        except KeyboardInterrupt:
            self.shutdown()


if __name__ == '__main__':
    rospy.init_node('dialogflow_mic_client')
    g = GspeechClient()
    g.start_client()

