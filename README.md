*****************************
**Inspiration**
*****************************
This app was inspired by another program made by Texas A&M students where they collected facial recognition data based on the individual's facial expressions and responses to stereotypical and not so stereotypical or more uncomfortable question types. Their data measured the change in uncertainty and how uncomfortable the individual became when they were asked a startling question and the program used that data to measure how uncertain an individual's face becomes in a game of poker to predict the game probability or outcomes. The main inspiration we took from this program was the idea behind wanting to implement facial recognition to solve a problem. Since productivity is an incredibly common issue, we wanted to focus on improving that using the facial recognition technology we were inspired by.  

*****************************
**What it does**
*****************************
_Overall Function:_

Our program tracks one's facial expressions, movements, and keystrokes over time to measure and evaluate their focus and fatigue levels for both individual sessions and over extended increments of time.
*****************************
_Calibration/Initial Launch:_

When you initially launch the application, you are instructed to calibrate the system according to your own personal facial expressions, movements, and keystrokes. A popup will open instructing you to position your face in frame and it will then measure your standard typing data for when you are focused for a 30 second time interval. Next, the popup will provide facial frame guidelines for when you tilt your head left, right, up, down, and back to center for 1 second each to grasp an idea of how you look like when you are either switching to focus on a task that isn't digital or if you are becoming unfocused altogether. If you cover your face with your hands or obstruct the view in any way, the calibration process automatically pauses and a notification pops up for the user to fix their position and calibration resumes once the user does so. After collecting the calibration data, the popup will automatically close and begin collecting data for the session. 
*****************************
_Session Data Collection:_

For each session, we continuously record through system camera to collect information on the facial framing and positioning. When recording we take 478 points on the user's face to serve as facial landmarks for parts such as eyes, mouth, eyebrows, etc. We have placed 52 facial expression "blendshape" scores into the program which are essentially the most common facial expressions people tend to make for varying levels of focus. We then organize the 478 facial points to one of the 52 blendshapes, combine it with the facial rotation data, then determine the output on how focused or fatigued an individual is. 

Of the 478 facial points we take, 6 landmarks are tracked around each eye to determine the EAR (or eye aspect ratio). The perclos (or percentage of eyelid closure) aspect records how long your eyes are closed to determine the total time for drowsiness which is essential for the fatigue feature. The MAR (or mouth aspect ratio) then records 4 landmarks: upper inner lip, lower inner lip, the left mouth corner, and the right mouth corner. The MAR is then used to determine focus and fatigue by analyzing how much an individual yawns, has their lips quiver, or has their lips nervously pressed up against each other. The eyebrow aspect keeps track of when an individual angrily scrunches their eyebrows or nervously raises their eyebrows and similar movements for focus and fatigue data. Lastly, the blink rate aspect tracks how often you blink for focus and fatigue data.
*****************************
_Post-Session Display:_

Once all of the data has been collected, all of it is displayed either graphically, in averages, highest peaks, lowest falls, or quantitative summaries.

For the current session, we display the total session time, possible stress periods, time spent highly focused, time spent with low fatigue, your average focus, and peak fatigue amount. The session data is then also compared to your overall all time focus data. 

All of our graphical data is presented in line graphs, one for the current session, and one for each increment of time. Each graph gives you the focus percentage, fatigue percentage, estimated stress percentage, possible stress periods, and times of lost focus. For the total data collected, we include the same information but for your overall day, week, month, and year. Since collecting facial recognition data and directly determining stress levels based on that is typically unreliable, we preferred to collect the fatigue and focus data first and then convert that into stress prediction data, but we don't prioritize this and leave it as an estimate due to the uncertainty. 

The session's quantitative summary is provided to you via an (adorable) penguin AI chatbot built using NVIDA's Nemotron. The chatbot first provides you a general summary of your fatigue, focus, and stress. It then provides recommendations based on your data and gives a report beneath it on how much camera, face, and keystroke data was collected.

Lastly, timing summaries and interesting moments to explore from your session are displayed at the very bottom.

*****************************
**How we built it**
*****************************
_Planning:_

We started off by brainstorming a program outline in the form of a flowchart. We used a top-down hierarchy for our program, starting off parent nodes with the most common things to track like facial rotation, expressions, and keystrokes. From there, we branched out into specifics on certain parts of your face and movements like explained previously, adding subsequent child nodes as necessary. 
*****************************
_Programming:_

For our actual program, we used various AI chatbots such as ChatGPT, Gemini, Claude, and Codex to generate our program. For the back-end development, we used Claude to assist with prompt engineering on Codex, meanwhile for the front-end development we used the ChatGPT Plus model from the free trial provided to us at this event and Claude. For the Machine Learning aspect of our program, we used Google's MediaPipe for the facial tracking.
*****************************
_Debugging:_

Each team member tested out our application and facial tracking features to properly calibrate and streamline our focus, fatigue, and predicted stress scores. We consistently entered prompts in order to debug our program, correcting technical, logical, and visual issues for our application. A majority of the back-end development was debugged also using Codex while a majority of the front-end development was debugged using ChatGPT Plus.
*****************************
**Challenges we ran into**

_Data Accuracy:_
A majority of the issues we faced were related to dealing with individuals with glasses and how it obstructs the eyebrow view. We had to repeatedly test data for individuals with glasses to refine our scores which then pushed us to include more forehead tracking points to avoid issues relating to wearing glasses. As previously mentioned, stress is the hardest factor to measure from facial points and the functions currently available are typically unreliable. Due to our repeated issues with the stress level accuracy, we eventually transitioned into stress level predictions based on the focus and fatigue levels collected instead of trying to directly calculate it from facial points. 

_Visuals and Graphics:_
For our calibration period, we realized that initially we never showed the user what input the camera was receiving, which caused the calibration to be less accurate since users might not be on camera properly. We offset this issue by including a calibration popup with the camera visual so users could see if they were in frame. We realized that people might move around on screen too much during calibration, so we added a face outline to serve as a guide for where to position your face relative to the screen. Then we realized that having a guide for only centering your face in a forward facing position might be confusing when being instructed to turn your head, so we included animations for turning your head too. 

For the visuals and displays, we initially focused on making this accessible to only Windows users, but we eventually realized font sizing and screen configuration were heavily misplaced for Mac users, so we spent some time debugging the Mac interface. 

Aside from the calibration interface and Mac accessibility, we fixed smaller issues in the UI such as typos, layering mistakes for the hover icons, font type, images, and theme cohesion. 

*****************************
**Accomplishments that we're proud of**
*****************************
We are incredibly proud of how accurately we managed to evaluate focus, fatigue, and stress using facial movements. We are also proud of the speed of the facial tracking itself and how much data we cover in such a short span of time. The feature we're probably the most proud of is how well we set up the calibration popup, especially the animation and guidance for the user. 

*****************************
**What we learned**
*****************************
We learned how to utilize various libraries and packages for this program: proxy_tools, flatbuffers, bottle, tzdata, typing_extensions, six, sentencepiece, pandas, pyparsing, pycparser, protobuf, pillow, packaging, opt_einsum, openai, opencv, nodejs, numpy, nvidia-nemotron, kiwisolver, fonttools, cycler, attrs, absl-py, scipy, python-datautil, pynput, opencv-contrib-python, ml-dtypes, contourpy, cffi, scikit-learn, sounddevice, sqlite, matplotlib, jaxlib, clr_loader, pythonnet, jax, pywebview, and mediapipe. 

_Webcam Processing:_

Mediapipe is by far the most important library we utilized in our entire code since it converts the webcam data into the various facial landmarks we used, which was then used to calculate our focus, fatigue, and predicted stress values. In order to use mediapipe, we used opencv-contrib-python to first open, process and convert the webcam data into usable information. 

_Keystroke Data Processing:_

The only library essential to keystroke data collection was pynput which takes typing data from any application open on your laptop. Some of the data collected using this library includes WPM, backspace ratio, and pause timings. 

_Graphical Displays:_

For our graph displays, we utilized numpy and matplotlib the most. Numpy was responsible for the mathematical calculations, meanwhile matplotlib took our calculations and presented them onto practical graphs for the users to view.

_Application Interface:_

Pywebview is probably the most important library imported for our program since it gives us the web-based interface from the app. This library is important for the app interface. 

_Machine Learning/AI:_

We had several packages responsible for the machine learning and AI aspect of this program, the main ones being pandas, scikit-learn, joblib, nvidia-nemotron, and openai. Scikit-learn is for the Machine Learning aspect, while nvidia-nemotron and openai are used for AI.

*****************************
**What's next for Flowstate**
*****************************

We would like to improve the program by improving the accuracy of our data, review quality and speed of our data, and hand movements. We didn't really implement much for fidgeting, posture, full body data collection, and working on handwritten notes or activities instead of digital ones. 
