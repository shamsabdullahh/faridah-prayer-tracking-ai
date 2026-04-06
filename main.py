import cv2
import mediapipe as mp
import speech_recognition as sr
import threading
import time

# Initialize MediaPipe Pose for movement tracking
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=0, enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# Initialize speech recognizer
recognizer = sr.Recognizer()

# Define prayer steps for each prayer
# Prayer steps for each prayer
def fajr_prayer():
    return ["Takbeer", "Standing", "Rukoo (Bowing)","Standing", "Sujood (Prostration)", "Standing","Sujood (Prostration)","Standing", "Salam"]
def dhuhr_prayer():
    return ["Takbeer", "Standing", "Rukoo (Bowing)","Standing", "Sujood (Prostration)", "Standing","Sujood (Prostration)",  "Standing", "Rukoo (Bowing)","Standing", "Sujood (Prostration)", "Standing","Sujood (Prostration)", "Standing","Takbeer", "Standing", "Rukoo (Bowing)","Standing", "Sujood (Prostration)", "Standing","Sujood (Prostration)",  "Standing", "Rukoo (Bowing)", "Standing","Sujood (Prostration)", "Standing","Sujood (Prostration)", "Standing","Salam"]

def asr_prayer():
    return dhuhr_prayer()

def maghrib_prayer():
    return fajr_prayer() + ["Takbeer", "Standing", "Rukoo (Bowing)","Standing", "Sujood (Prostration)", "Standing","Sujood (Prostration)","Standing", "Salam"]

def isha_prayer():
    return dhuhr_prayer()
# List of available prayers
PRAYERS = {
    "Fajr": fajr_prayer,
    "Dhuhr": dhuhr_prayer,
    "Asr" :asr_prayer,
    "Maghrib" :maghrib_prayer,
    "Isha" :isha_prayer
}

# Helper function to calculate Euclidean distance
def calculate_distance(point1, point2):
    return ((point1.x - point2.x)**2 + (point1.y - point2.y)**2)**0.5

# Adjust thresholds dynamically based on height
def adjust_thresholds_based_on_height(height):
    scale = height / 1.3
    return {
        "takbeer_dist": 0.2 * scale,
        "standing_dist": 0.16 * scale,
        "rukoo_dist": 0.1 * scale,
        "nose_knee_distance": 0.08 * scale,
    }

# Check if a landmark is valid
def is_valid_landmark(landmark):
    return landmark is not None and hasattr(landmark, 'y')

# Estimate height dynamically
def estimate_height(landmarks):
    head_to_foot = calculate_distance(
        landmarks[mp_pose.PoseLandmark.NOSE.value],
        landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value]
    )
    return head_to_foot

# Movement detection functions
def detect_takbeer(landmarks, thresholds):
    left_hand_shoulder_dist = calculate_distance(
        landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value],
        landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
    )
    right_hand_shoulder_dist = calculate_distance(
        landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value],
        landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
    )
    return left_hand_shoulder_dist < thresholds["takbeer_dist"] and right_hand_shoulder_dist < thresholds["takbeer_dist"]

def detect_standing(landmarks, thresholds):
    head_above_hips = (
        landmarks[mp_pose.PoseLandmark.NOSE.value].y < landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y and
        landmarks[mp_pose.PoseLandmark.NOSE.value].y < landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y
    )
    wrists_near_body = (
        abs(landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x - landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x) < 0.25 and
        abs(landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x - landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x) < 0.25
    )
    return head_above_hips and wrists_near_body

def detect_rukoo(landmarks, thresholds):
    left_hand_knee_dist = calculate_distance(
        landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value],
        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value]
    )
    right_hand_knee_dist = calculate_distance(
        landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value],
        landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value]
    )
    return left_hand_knee_dist < thresholds["rukoo_dist"] and right_hand_knee_dist < thresholds["rukoo_dist"]

def detect_sujood(landmarks, thresholds):
    nose_near_ground = (
        landmarks[mp_pose.PoseLandmark.NOSE.value].y > 
        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y
    )
    hips_above_knees = (
        landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y < 
        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y
    )
    return nose_near_ground and hips_above_knees

def detect_prayer_position(landmarks, thresholds):
    if detect_takbeer(landmarks, thresholds):
        return "Takbeer"
    elif detect_standing(landmarks, thresholds):
        return "Standing"
    elif detect_rukoo(landmarks, thresholds):
        return "Rukoo (Bowing)"
    elif detect_sujood(landmarks, thresholds):
        return "Sujood (Prostration)"
    return "Unknown"

# Compare sequences
def compare_sequences(correct_sequence, executed_sequence):
    correct_count = 0
    for correct_step, executed_step in zip(correct_sequence, executed_sequence):
        if correct_step == executed_step:
            correct_count += 1
    accuracy = (correct_count / len(correct_sequence)) * 100
    return accuracy

# Voice recognition function
def recognize_audio(correct_sequence, executed_sequence, salam_count, stop_event):
    mic = sr.Microphone()
    while not stop_event.is_set():
        with mic as source:
            recognizer.adjust_for_ambient_noise(source)
            try:
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio, language='ar')
                print(f"Recognized text: {text}")

                if text.strip() == "السلام عليكم ورحمه الله":
                    salam_count[0] += 1
                    executed_sequence.append("Salam")
                    print(f"Salam count: {salam_count[0]}")
                    if salam_count[0] == 2:
                        stop_event.set()
                        return
            except sr.UnknownValueError:
                print("Could not understand the audio.")
            except sr.WaitTimeoutError:
                print("Listening timeout.")
            except sr.RequestError as e:
                print(f"Speech recognition error: {e}")

# Main tracking function
def track_prayer(prayer_name):
    if prayer_name not in PRAYERS:
        print(f"Error: Prayer '{prayer_name}' not found.")
        return

    correct_sequence = PRAYERS[prayer_name]()
    executed_sequence = []
    detected_step = None
    last_detection_time = time.time()
    salam_count = [0]
    stop_event = threading.Event()

    threading.Thread(target=recognize_audio, args=(correct_sequence, executed_sequence, salam_count, stop_event)).start()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Camera not accessible")
        return

    height = None
    thresholds = None

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        results = pose.process(frame)

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            if height is None:
                height = estimate_height(landmarks)
                thresholds = adjust_thresholds_based_on_height(height)
                print(f"Estimated height: {height:.2f} meters")

            step = detect_prayer_position(landmarks, thresholds)

            if step != "Unknown" and step != detected_step:
                if time.time() - last_detection_time > 4:
                    detected_step = step
                    executed_sequence.append(step)
                    print(f"Detected Step: {step}")
                    last_detection_time = time.time()

            mp_drawing.draw_landmarks(frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        cv2.putText(frame, f"Detected: {detected_step}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Prayer Tracking", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop_event.set()
            break

    cap.release()
    cv2.destroyAllWindows()

    accuracy = compare_sequences(correct_sequence, executed_sequence)
    print(f"Prayer completed! Accuracy: {accuracy:.2f}%")
    if accuracy >= 70:
        print("الصلاة اكتملت! الحمد لله.")
    else:
        print("لم تكتمل الصلاة بدقة كافية، الرجاء المحاولة مرة أخرى.")

# Example Usage
if __name__ == "__main__":
    track_prayer("Fajr")

