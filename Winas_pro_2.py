import pygame
import pyttsx3
import subprocess
import sys
import threading
import time
import os
from vosk import Model, KaldiRecognizer
import pyaudio
import platform
import google.generativeai as genai
import math

# --- Configuration ---
ASSISTANT_NAME = "friday"
YOUR_API_KEY = "AIzaSyD2SBuHvZCYPNs0810w_Yg3FVeVYUSehnw" # Your key is here

# --- Global State Variable for GUI ---
ASSISTANT_STATE = "IDLE"

# --- AI and Vosk Setup ---
genai.configure(api_key=YOUR_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

VOSK_MODEL_PATH_SMALL = "E:\\study\\vosk-model-small-en-us-0.15"
VOSK_MODEL_PATH_LARGE = "E:\\study\\vosk-model-en-us-0.42-gigaspeech"

if os.path.exists(VOSK_MODEL_PATH_SMALL):
    VOSK_MODEL_PATH = VOSK_MODEL_PATH_SMALL
    print("Loading FAST small Vosk model.")
else:
    VOSK_MODEL_PATH = VOSK_MODEL_PATH_LARGE
    print("Small model not found. Loading LARGE (slower startup) Vosk model.")

# --- Automatic App Discovery ---
def scan_for_apps():
    print("Scanning for installed applications...")
    apps = {"notepad": "notepad.exe", "calculator": "calc.exe"}
    start_menu_paths = [
        os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs"),
        os.path.join(os.environ["ALLUSERSPROFILE"], "Microsoft\\Windows\\Start Menu\\Programs"),
    ]
    for path in start_menu_paths:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith((".lnk", ".exe")):
                    app_name = os.path.splitext(file)[0].lower()
                    if app_name not in apps: apps[app_name] = os.path.join(root, file)
    print(f"Found {len(apps)} applications.")
    return apps
APP_LAUNCHERS = scan_for_apps()

# --- Core Functions ---
tts_engine = pyttsx3.init()
p_audio = pyaudio.PyAudio()

def execute_command(path_to_app):
    try: os.startfile(path_to_app)
    except Exception as e: speak(f"Sorry, I had trouble opening that."); print(e)

def speak(text):
    global ASSISTANT_STATE
    ASSISTANT_STATE = "IDLE"
    print(f"Assistant: {text}")
    tts_engine.say(text)
    tts_engine.runAndWait()

def get_ai_response(prompt):
    global ASSISTANT_STATE
    ASSISTANT_STATE = "THINKING"
    try:
        response = ai_model.generate_content(prompt)
        return response.text.replace('*', '').replace('`', '')
    except Exception as e:
        print(f"AI API Error: {e}")
        return "I'm having trouble connecting to my brain right now."

# --- Voice Assistant Logic (Runs in a background thread) ---
def run_assistant_logic():
    global ASSISTANT_STATE
    try:
        model = Model(VOSK_MODEL_PATH)
        recognizer = KaldiRecognizer(model, 16000)
    except Exception as e: print(f"Vosk Error: {e}"); return

    while True:
        # 1. Listen for Wake Word
        mic_stream = p_audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4096)
        print(f"\nListening for wake word '{ASSISTANT_NAME}'...")
        recognizer.SetWords(True)
        while True:
            data = mic_stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = eval(recognizer.Result())
                if ASSISTANT_NAME in result.get('text', ''):
                    ASSISTANT_STATE = "LISTENING"
                    speak("Yes?")
                    break
        mic_stream.close()

        # 2. Listen for Command
        mic_stream = p_audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4096)
        print("Now listening for a command...")
        recognizer.SetWords(False)
        last_heard_time = time.time()
        command_processed = False
        while time.time() - last_heard_time < 7:
            data = mic_stream.read(4096, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = eval(recognizer.Result())
                text = result.get('text', '').strip()
                if text:
                    process_command(text)
                    command_processed = True
                    break
        mic_stream.close()
        
        if not command_processed: speak("I didn't hear anything.")
        ASSISTANT_STATE = "IDLE"
        time.sleep(1)

def process_command(text):
    """ This is the final, smartest version of the command processor. """
    text = text.lower()
    print(f"Processing command: '{text}'")
    if "goodbye" in text or "shut down" in text:
        speak("Goodbye!")
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return

    # --- THIS IS THE NEW, SMARTER APP LAUNCHING LOGIC ---
    if text.startswith("open "):
        app_to_open = text[5:].strip()
        # Loop through all found apps to find a partial match
        for app_key, app_path in APP_LAUNCHERS.items():
            if app_to_open in app_key:
                speak(f"Opening {app_key}.") # Speak the full, correct name
                execute_command(app_path)
                return # Exit the function since the command is handled
    
    # If no local command was found, send to the AI
    ai_answer = get_ai_response(text)
    speak(ai_answer)

# --- Pygame GUI Logic (Runs on the main thread) ---
def run_gui():
    pygame.init()
    info = pygame.display.Info()
    win_size = 200
    win_pos_x = (info.current_w - win_size) // 2
    win_pos_y = (info.current_h - win_size) // 2
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{win_pos_x},{win_pos_y}"
    
    window = pygame.display.set_mode((win_size, win_size), pygame.NOFRAME)
    pygame.display.set_caption("Friday AI")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        window.fill((0, 0, 0))

        if ASSISTANT_STATE != "IDLE":
            window.set_colorkey((0,0,0))
            current_time = pygame.time.get_ticks()
            if ASSISTANT_STATE == "LISTENING":
                radius = 60 + 20 * math.sin(current_time * 0.003)
                pygame.draw.circle(window, (0, 100, 255), (win_size // 2, win_size // 2), int(radius), 8)
            elif ASSISTANT_STATE == "THINKING":
                arc_angle = (current_time // 4) % 360
                rect = pygame.Rect(50, 50, 100, 100)
                pygame.draw.arc(window, (255, 150, 0), rect, math.radians(arc_angle), math.radians(arc_angle + 120), 10)
                pygame.draw.arc(window, (255, 150, 0), rect, math.radians(arc_angle + 180), math.radians(arc_angle + 300), 10)
        else:
            window.set_colorkey((1,1,1))
            window.fill((1,1,1))
            
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

# --- Main Execution Block ---
if __name__ == "__main__":
    assistant_thread = threading.Thread(target=run_assistant_logic, daemon=True)
    assistant_thread.start()
    run_gui()