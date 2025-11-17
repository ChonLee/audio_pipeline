import os
import logging
import threading
from flask import Flask, render_template, request, jsonify, Response
from processor import split_and_export
from queue import Queue, Empty
import uuid
from ftplib import FTP
from config.settings import FTP_LOCATIONS  # your settings.py with FTP_PASS etc.
from processor import upload_files_to_ftp

UPLOAD_FOLDER = "/app/uploads"
PROCESSED_FOLDER = "/app/processed"

# --- TESTING ONLY: clear processed and uploads folders on startup ---
# Comment out these lines when not testing
for folder in ["processed", "uploads"]:
    folder_path = os.path.join(os.getcwd(), folder)
    if os.path.exists(folder_path):
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logging.info(f"Deleted {file_path} (testing cleanup)")
            except Exception as e:
                logging.warning(f"Failed to delete {file_path}: {e}")
# --- TESTING ONLY---



app = Flask(__name__, template_folder="app/templates")
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Dictionary to store per-job progress queues
jobs = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    date_str = request.form.get("date_str")
    wav_file = request.files.get("wav_file")
    artwork_file = request.files.get("artwork_file")
    show_title = request.form.get("show_title")
    guest = request.form.get("guest")

    if not wav_file:
        logging.warning("No WAV file uploaded!")
        return jsonify(success=False, message="No WAV file uploaded!"), 400

    # Save uploaded files
    wav_path = os.path.join(app.config['UPLOAD_FOLDER'], wav_file.filename)
    wav_file.save(wav_path)
    artwork_path = None
    if artwork_file:
        artwork_path = os.path.join(app.config['UPLOAD_FOLDER'], artwork_file.filename)
        artwork_file.save(artwork_path)

    # Create a unique job ID and queue
    job_id = str(uuid.uuid4())
    job_queue = Queue()
    jobs[job_id] = job_queue

    # Start processing in a separate thread
    thread = threading.Thread(
        target=process_audio,
        args=(date_str, wav_path, artwork_path, show_title, guest, job_queue)
    )
    thread.start()

    return jsonify(success=True, message="Upload successful. Processing started.", job_id=job_id)



def get_processed_files(date_str, sbe_number=None):
    """Return paths for all processed files based on date_str (Monday)."""
    base_path = app.config['PROCESSED_FOLDER']

    # Saturday before Monday
    saturday_str = get_saturday_before(date_str)

    wav_files = [
        f"{base_path}/stevebrown_{saturday_str}_S1_Sirius.wav",
        f"{base_path}/stevebrown_{saturday_str}_S2_Sirius.wav",
        f"{base_path}/stevebrown_{saturday_str}_S3_Sirius.wav",
        f"{base_path}/stevebrown_{saturday_str}_S4_Sirius.wav",
        f"{base_path}/stevebrown_{saturday_str}_S5_Sirius.wav",
    ]
    
    h1_mp3 = f"{base_path}/stevebrown_{saturday_str}_H1.mp3"

    # If SBE number isn’t provided, compute it
    if sbe_number is None:
        sbe_number = get_sbe_number(date_str)

    # Podcast uses Monday
    monday_str = format_monday(date_str)
    podcast = f"{base_path}/sbe{sbe_number}-{monday_str}.mp3"
    
    return h1_mp3, wav_files, podcast


# def process_audio(date_str, wav_path, artwork_path, show_title, guest, progress_queue):
#     """
#     Process audio and push progress messages into the given queue,
#     then upload to all FTP sites.
#     """
#     def progress(msg):
#         logging.info(msg)
#         progress_queue.put(msg)

#     try:
#         progress("⏳ Starting processing...")

#         # Process audio
#         result = split_and_export(
#             wav_path,
#             app.config['PROCESSED_FOLDER'],
#             date_str,
#             show_title,
#             guest,
#             artwork_path,
#             progress_callback=progress
#         )

#         # Unpack files
#         if result and len(result) == 3:
#             wav_files, mp3_files, podcast_file = result
#             progress(f"✅ Processing complete!")
#             progress(f"WAV segments: {', '.join(wav_files)}")
#             progress(f"MP3 files: {', '.join(mp3_files)}")
#             progress(f"Podcast file: {podcast_file}")
#         else:
#             # fallback
#             h1_mp3, wav_files, podcast_file = get_processed_files(date_str)
#             progress("✅ Processing complete! (using default filenames)")

#         # --- FTP Uploads ---
#         for site, cfg in FTP_LOCATIONS.items():
#             if site == "srn":
#                 files_to_upload = [h1_mp3] + wav_files
#                 ftp_upload(files_to_upload, **cfg, progress=progress)

#             elif site == "ambos":
#                 # Upload H1 twice with renamed files
#                 rename_noncom = {os.path.basename(h1_mp3): os.path.basename(h1_mp3).replace("_H1.mp3", "_NONCOM.mp3")}
#                 rename_com = {os.path.basename(h1_mp3): os.path.basename(h1_mp3).replace("_H1.mp3", "_COM.mp3")}
#                 ftp_upload([h1_mp3], **cfg, rename=rename_noncom, progress=progress)
#                 ftp_upload([h1_mp3], **cfg, rename=rename_com, progress=progress)

#             elif site == "kln":
#                 ftp_upload([podcast_file], **cfg, progress=progress)

#         progress("🎉 All uploads complete!")

#     except Exception as e:
#         progress(f"❌ Error during processing: {e}")
#     finally:
#         progress_queue.put("[DONE]")

def process_audio(date_str, wav_path, artwork_path, show_title, guest, progress_queue):
    """
    Process audio and push progress messages into the given queue,
    then upload to all FTP sites using the refactored upload function.
    """
    def progress(msg):
        logging.info(msg)
        progress_queue.put(msg)

    try:
        progress("⏳ Starting processing...")

        # Process audio
        result = split_and_export(
            wav_path,
            app.config['PROCESSED_FOLDER'],
            date_str,
            show_title,
            guest,
            artwork_path,
            progress_callback=progress
        )

        # Unpack files
        if result and len(result) == 3:
            wav_files, mp3_files, podcast_file = result
            h1_mp3 = mp3_files[0]
            progress(f"✅ Processing complete!")
            progress(f"WAV segments: {', '.join(wav_files)}")
            progress(f"MP3 files: {', '.join(mp3_files)}")
            progress(f"Podcast file: {podcast_file}")
        else:
            # fallback if split_and_export fails
            h1_mp3, wav_files, podcast_file = get_processed_files(date_str)
            progress("✅ Processing complete! (using default filenames)")

        # --- FTP Uploads using refactored function ---
        upload_files_to_ftp(h1_mp3, wav_files, podcast_file, progress_callback=progress)

    except Exception as e:
        progress(f"❌ Error during processing: {e}")
    finally:
        progress_queue.put("[DONE]")


@app.route("/process-audio-sse/<job_id>")
def process_audio_sse(job_id):
    """SSE endpoint to stream progress messages for a specific job."""
    if job_id not in jobs:
        return f"No such job: {job_id}", 404

    progress_queue = jobs[job_id]

    def generate():
        while True:
            try:
                msg = progress_queue.get(timeout=0.5)
                yield f"data: {msg}\n\n"
                if msg == "[DONE]":
                    del jobs[job_id]
                    break
            except Empty:
                continue

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
