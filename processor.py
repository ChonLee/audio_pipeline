import os
import logging
import time
from datetime import datetime, timedelta
from pydub import AudioSegment, effects
from pydub.silence import detect_silence
import ftplib
from config.settings import FTP_LOCATIONS
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TRCK, TCON, COMM, APIC, ID3NoHeaderError


SILENCE_MS = 1500

SEGMENTS = [
    {"name": "S1", "start": 6, "end": 18},
    {"name": "S2", "start": 21, "end": 30},
    {"name": "S3", "start": 34, "end": 41},
    {"name": "S4", "start": 44, "end": 53},
    {"name": "S5", "start": 55.0067, "end": 58.833},
]

MONDAY_SEGMENTS = [
    {"start": 6, "end": 19},
    {"start": 21, "end": 30.99783333333333},
    {"start": 34, "end": 42},
    {"start": 44, "end": 54},
    {"start": 55, "end": 58.833},
]

def get_sbe_number(date_str=None):
    """
    Calculate the SBE number based on the Monday date.
    
    :param date_str: optional, format "mm-dd-yy"; defaults to today
    :return: SBE number as string
    """
    # Base reference Monday and its SBE number
    base_monday = datetime.strptime("06-17-24", "%m-%d-%y")  # known Monday
    base_sbe = 900

    # Use today if date_str is not provided
    if not date_str:
        date_str = datetime.today().strftime("%m-%d-%y")

    target_date = datetime.strptime(date_str, "%m-%d-%y")

    # Get the Monday of the target week
    days_to_monday = 0 - target_date.weekday()
    target_monday = target_date + timedelta(days=days_to_monday)

    # Number of weeks difference
    delta_weeks = (target_monday - base_monday).days // 7

    sbe_number = base_sbe + delta_weeks
    return str(sbe_number)

def format_monday(date_str):
    dt = datetime.strptime(date_str, "%m-%d-%y")
    return dt.strftime("%m%d%Y")

def get_sunday_before(date_str):
    dt = datetime.strptime(date_str, "%m-%d-%y")
    sunday = dt - timedelta(days=1)  # Saturday - 1 day
    return sunday.strftime("%B %-d, %Y")  # e.g., April 9, 2023

def get_saturday_before(date_str):
    dt = datetime.strptime(date_str, "%m-%d-%y")
    saturday = dt - timedelta(days=2)
    return saturday.strftime("%m-%d-%y")  

# def ftp_upload(file_paths, host, user, password, remote_dir="/", rename=None, max_retries=2):
#     """
#     Upload files to FTP server (plain FTP for testing) with retry.
#     One FTP connection per file to avoid TLS session issues.
#     """
#     for file_path in file_paths:
#         filename = os.path.basename(file_path)

#         # Determine files to upload (rename or plain)
#         upload_files = [filename]
#         if rename:
#             upload_files = [filename.replace("H1", tag) for tag in rename]

#         for up_file in upload_files:
#             for attempt in range(1, max_retries + 1):
#                 try:
#                     logging.info(f"Connecting to {host} for {up_file} (attempt {attempt})")
#                     ftp = FTP(host, timeout=30)
#                     ftp.login(user, password)
#                     ftp.set_pasv(True)
#                     ftp.cwd(remote_dir)

#                     logging.info(f"Uploading {up_file} to {host}")
#                     with open(file_path, "rb") as f:
#                         ftp.storbinary(f"STOR {up_file}", f)

#                     logging.info(f"✅ Successfully uploaded {up_file}")
#                     ftp.quit()
#                     break
#                 except Exception as e:
#                     logging.error(f"Error uploading {up_file} to {host}: {e}")
#                     try:
#                         ftp.quit()
#                     except:
#                         pass
#                     if attempt < max_retries:
#                         logging.info("Retrying...")
#                         time.sleep(2)  # short delay before retry
#                     else:
#                         logging.error(f"❌ Failed to upload {up_file} after {max_retries} attempts")

def ftp_upload(files, host, user, password, remote_dir,
               rename=None, max_retries=3, progress=None):
    """
    Upload files to an FTP server with retry and remote file-size verification.
    Raises an exception if upload fails after retries.
    """

    if progress is None:
        progress = lambda msg: print(msg)

    # Support renaming
    rename_map = {}
    if isinstance(rename, dict):
        rename_map = rename

    with ftplib.FTP(host) as ftp:
        ftp.login(user=user, passwd=password)
        ftp.cwd(remote_dir)

        for file_path in files:
            filename_local = os.path.basename(file_path)
            filename_remote = rename_map.get(filename_local, filename_local)

            local_size = os.path.getsize(file_path)

            for attempt in range(1, max_retries + 1):
                try:
                    progress(f"Uploading {filename_remote} (Attempt {attempt}/{max_retries})...")

                    with open(file_path, "rb") as f:
                        ftp.storbinary(f"STOR {filename_remote}", f)

                    # ---- VERIFY REMOTE FILE SIZE ----
                    remote_size = ftp.size(filename_remote)

                    if remote_size != local_size:
                        raise Exception(
                            f"File size mismatch: local={local_size}, remote={remote_size}"
                        )

                    progress(f"✓ Verified: {filename_remote} uploaded successfully.")
                    break

                except Exception as e:
                    progress(f"⚠️ Error uploading {filename_remote}: {e}")

                    if attempt == max_retries:
                        raise Exception(
                            f"Upload failed after {max_retries} attempts: {filename_remote}"
                        )

                    time.sleep(2)


def split_and_export(wav_path, output_dir, date_str, show_title="", guest="", artwork_path=None, progress_callback=None):
    def log(msg):
        logging.info(msg)
        if progress_callback:
            progress_callback(msg)

    audio = AudioSegment.from_wav(wav_path)

    # --- Export H1 ---
    log("Starting H1 MP3 export...")
    h1_audio = audio[0:int(58.833*60*1000)]
    h1_file = os.path.join(output_dir, f"stevebrown_{get_saturday_before(date_str)}_H1.mp3")
    h1_audio.export(h1_file, format="mp3", bitrate="320k")
    log(f"H1 exported: {h1_file}")

    # --- Export Sirius segments ---
    wav_files = []
    for seg in SEGMENTS:
        start_ms = int(seg["start"]*60*1000)
        end_ms = int(seg["end"]*60*1000)
        segment_audio = audio[start_ms:end_ms] #+ AudioSegment.silent(duration=SILENCE_MS)
        wav_file = os.path.join(output_dir, f"stevebrown_{get_saturday_before(date_str)}_{seg['name']}_Sirius.wav")
        segment_audio.export(wav_file, format="wav")
        wav_files.append(wav_file)
        log(f"Sirius segment exported: {wav_file}")

    # --- Export Monday podcast ---
    podcast_audio = AudioSegment.silent(0)
    for seg in MONDAY_SEGMENTS:
        start_ms = int(seg["start"]*60*1000)
        end_ms = int(seg["end"]*60*1000)
        podcast_audio += audio[start_ms:end_ms] #+ AudioSegment.silent(duration=SILENCE_MS)

    # Remove extra silence at the start/end and compress long pauses
    # podcast_audio = effects.strip_silence(
    #     podcast_audio,
    #     silence_len=1000,  # minimum silence to consider (ms)
    #     silence_thresh=-40  # anything quieter than this dBFS is silence
    # )

    podcast_file = os.path.join(output_dir, f"sbe{get_sbe_number(date_str)}-{format_monday(date_str)}.mp3")
    podcast_audio.export(podcast_file, format="mp3", bitrate="96k", parameters=["-ar","44100"])
    log(f"Podcast exported: {podcast_file}")

    # --- ID3 tagging ---
    log("Applying ID3 tags to Podcast...")
    if apply_id3_tags(podcast_file, date_str, show_title, guest):
        log(f"✅ ID3 tags applied to {podcast_file}")
    else:
        log(f"❌ Failed to apply ID3 tags to {podcast_file}")


    mp3_files = [h1_file, podcast_file]

    return wav_files, mp3_files, podcast_file


# def upload_files_to_ftp(h1_file, wav_files, podcast_file, progress_callback=None):
#     def log(msg):
#         if progress_callback:
#             progress_callback(msg)
#         else:
#             logging.info(msg)

#     # --- SRN Upload ---
#     log("Uploading to SRN...")
#     ftp_upload([h1_file] + wav_files,
#                host=FTP_LOCATIONS["srn"]["host"],
#                user=FTP_LOCATIONS["srn"]["user"],
#                password=FTP_LOCATIONS["srn"]["password"],
#                remote_dir=FTP_LOCATIONS["srn"]["remote_dir"])
#     log("SRN upload complete!")

#     # --- AMBOS Upload ---
#     log("Uploading to AMBOS (NONCOM/COM)...")
#     for tag in ["NONCOM", "COM"]:
#         ftp_upload([h1_file],
#                    host=FTP_LOCATIONS["ambos"]["host"],
#                    user=FTP_LOCATIONS["ambos"]["user"],
#                    password=FTP_LOCATIONS["ambos"]["password"],
#                    remote_dir=FTP_LOCATIONS["ambos"]["remote_dir"],
#                    rename=[tag])
#     log("AMBOS upload complete!")

#     # --- KLN Upload ---
#     log("Uploading podcast to KLN...")
#     ftp_upload([podcast_file],
#                host=FTP_LOCATIONS["kln"]["host"],
#                user=FTP_LOCATIONS["kln"]["user"],
#                password=FTP_LOCATIONS["kln"]["password"],
#                remote_dir=FTP_LOCATIONS["kln"]["remote_dir"])
#     log("KLN upload complete!")

#     log("🎉 All uploads complete!")

def upload_files_to_ftp(h1_mp3, wav_files, podcast_file, progress_callback=None, max_retries=3):
    """
    Uploads processed files to all configured FTP sites.
    Raises an exception if any upload fails after retries.

    :param h1_mp3: path to H1 MP3
    :param wav_files: list of WAV segment paths
    :param podcast_file: path to podcast MP3
    :param progress_callback: optional function for logging
    :param max_retries: number of retry attempts per file
    """
    def progress(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            logging.info(msg)

    errors = []

    for site, cfg in FTP_LOCATIONS.items():
        try:
            if site == "srn":
                files_to_upload = [h1_mp3] + wav_files
                progress(f"Uploading to {site.upper()}...")
                ftp_upload(files_to_upload, **cfg, max_retries=max_retries, progress=progress)

            elif site == "ambos":
                progress(f"Uploading to {site.upper()} (NONCOM/COM)...")
                for tag in ["NONCOM", "COM"]:
                    rename_map = {os.path.basename(h1_mp3): os.path.basename(h1_mp3).replace("_H1.mp3", f"_{tag}.mp3")}
                    ftp_upload([h1_mp3], **cfg, rename=rename_map, max_retries=max_retries, progress=progress)

            elif site == "kln":
                progress(f"Uploading podcast to {site.upper()}...")
                ftp_upload([podcast_file], **cfg, max_retries=max_retries, progress=progress)

        except Exception as e:
            error_msg = f"❌ FTP upload failed for site {site}: {e}"
            progress(error_msg)
            errors.append(error_msg)

    if errors:
        # Raise an exception if any site failed
        raise RuntimeError("One or more FTP uploads failed:\n" + "\n".join(errors))

    progress("🎉 All FTP uploads completed successfully!")


def apply_id3_tags(mp3_file, date_str, show_title, guest, artwork_path="assets/album_art.png"):
    """
    Apply full ID3 tags to the given MP3 file.

    Includes:
    - Title: SBE number | date | show_title | guest
    - Artist: Steve Brown
    - Album: Steve Brown, Etc.
    - Track: SBE number
    - Year: current year
    - Genre: Podcast - Talk
    - Comment: © & ℗ current year Key Life Network http://www.KeyLife.org
    - Cover Art (optional)
    """
    try:
        # Dynamic values
        show_number = get_sbe_number(date_str)
        sunday_date = get_sunday_before(date_str)  # e.g., "May 25, 2025"
        current_year = str(datetime.now().year)

 
        # Extract year from the date_str
        dt = datetime.strptime(date_str, "%m-%d-%y")
        year_from_date = dt.year  # 4-digit year

        title_text = f"SBE{show_number} | {sunday_date} | {show_title} | {guest}"
        comment_text = f"© & ℗ {year_from_date} Key Life Network http://www.KeyLife.org"

        # Load existing tags or create new
        try:
            audio = ID3(mp3_file)
        except ID3NoHeaderError:
            audio = ID3()

        # --- Set core metadata ---
        audio.add(TIT2(encoding=3, text=title_text))    # Title
        audio.add(TPE1(encoding=3, text="Steve Brown")) # Artist
        audio.add(TALB(encoding=3, text="Steve Brown, Etc."))  # Album
        audio.add(TRCK(encoding=3, text=str(show_number)))      # Track
        audio.add(TDRC(encoding=3, text=str(year_from_date)))         # Year
        audio.add(TCON(encoding=3, text="Podcast - Talk"))     # Genre
        #audio.add(COMM(encoding=3, desc="Comment", text=comment_text))  # Comment
        #audio.add(COMM(encoding=1, lang="eng", desc="Comment", text=comment_text))

        # Comment frame — use UTF-16 for Mp3tag compatibility
        audio.add(COMM(encoding=1, lang="eng", desc="", text=comment_text))

        # --- Embed album art ---
        if os.path.exists(artwork_path):
            with open(artwork_path, "rb") as img:
                audio.add(APIC(
                    encoding=3,
                    mime="image/png",
                    type=3,       # front cover
                    desc="Cover",
                    data=img.read()
                ))

        # Save all tags
        audio.save(mp3_file)
        return True

    except Exception as e:
        logging.error(f"Error applying ID3 tags to {mp3_file}: {e}")
        return False