🧩 Selfie Puzzle Game
A Computer Vision and Game Development project built with Python, OpenCV, MediaPipe, NumPy, and Pygame.
Capture a selfie using hand gestures, automatically convert it into a shuffled 3×3 puzzle, and solve it using drag-and-drop interactions.

📌 Project Overview
Selfie Puzzle Game combines Computer Vision, Hand Gesture Recognition, Image Processing, and Game Development into a single interactive application.
The user selects a region from the webcam feed using pinch gestures detected by MediaPipe. The selected image is automatically divided into puzzle pieces, shuffled, and presented as a drag-and-drop puzzle game.
Technologies Demonstrated
Computer Vision using OpenCV
Real-Time Hand Tracking using MediaPipe
Gesture-Based User Interaction
Image Cropping and Processing
Puzzle Generation Algorithms
Game Development using Pygame

🎥 Project Workflow
Launch Application
        ↓
Open Webcam
        ↓
Detect Hand Landmarks
        ↓
Pinch Gesture Detected
        ↓
Draw Selection Rectangle
        ↓
Capture Selected Region
        ↓
Split Image into 9 Pieces
        ↓
Shuffle Puzzle Pieces
        ↓
Launch Puzzle Interface
        ↓
Solve Using Drag-and-Drop
        ↓
Victory Animation 🎉

✨ Features
Computer Vision Features
Real-time webcam feed
MediaPipe hand tracking
Pinch gesture detection
Gesture-based region selection
Image capture and cropping
Puzzle Features
Automatic 3×3 puzzle generation
Randomized puzzle shuffling
Drag-and-drop interactions
Move counter
Live timer
Puzzle preview mode
Restart functionality
Puzzle completion detection
Victory animation

📂 Project Structure
selfie-puzzle-game/
│
├── main.py
├── camera.py
├── gesture.py
├── capture.py
├── puzzle.py
├── game.py
├── requirements.txt
└── README.md

File Responsibilities
File	Purpose
main.py	Application entry point and workflow control
camera.py	Webcam initialization and frame capture
gesture.py	MediaPipe hand tracking and pinch detection
capture.py	Selection box creation and management
puzzle.py	Puzzle generation, shuffling, and validation
game.py	Drag-and-drop interface and game logic

🛠️ Tech Stack
Technology	Purpose
Python	Core programming language
OpenCV	Webcam access and image processing
MediaPipe	Hand landmark detection
NumPy	Image and array manipulation
Pygame	Game interface and rendering

🚀 Installation
Clone the Repository
git clone https://github.com/krishaagor-source/selfie-puzzle-game.git
cd selfie-puzzle-game
Create a Virtual Environment
python -m venv venv
Activate the Environment
macOS / Linux
source venv/bin/activate
Windows
venv\Scripts\activate
Install Dependencies
pip install -r requirements.txt

▶️ Running the Application
python main.py

🎮 How to Use
Phase 1 — Capture Your Selfie
Gesture	Action
Pinch & Hold	Start selection rectangle
Drag While Pinching	Resize selection area
Release Pinch	Lock rectangle
Pinch Inside Rectangle	Capture image
ESC / Q	Exit application

Phase 2 — Solve the Puzzle
Action	Result
Drag Piece	Pick up tile
Drop Piece	Swap positions
Hold Preview	Show original image
Restart	Reshuffle puzzle
ESC / Q	Exit game

⚙️ Configuration
Parameter	Default	Description
camera_index	0	Webcam device index
pinch_threshold	0.06	Pinch gesture sensitivity
piece_size	160	Puzzle tile size in pixels
GRID_SIZE	3	Puzzle dimensions

🏗️ System Architecture
main.py
│
├── Capture Phase
│     │
│     ├── Camera Module
│     ├── Gesture Detector
│     └── Frame Capture Logic
│
└── Puzzle Phase
      │
      ├── Puzzle Generator
      ├── Shuffle Engine
      └── Game Interface
      
🎯 Learning Outcomes
This project demonstrates practical implementation of:
Computer Vision using OpenCV
Hand Gesture Recognition
Real-Time Image Processing
Object-Oriented Programming
Event-Driven Programming
Human-Computer Interaction
Puzzle Generation Algorithms
Game Development with Pygame

🔮 Future Improvements
Support for 4×4 and 5×5 puzzle modes
Global leaderboard system
Save and track best completion times
Sound effects and music
Face-detection-assisted cropping
Mobile application version
Multiplayer challenge mode
AI-assisted puzzle difficulty adjustment

🤝 Contributing
Contributions are welcome.
Fork the repository
Create a new branch
Commit your changes
Open a Pull Request

📄 License
This project is licensed under the MIT License.

👩‍💻 Author
Krisha Gor
BSc IT Student | Aspiring AI Engineer | Computer Vision Enthusiast
GitHub: https://github.com/krishaagor-source
