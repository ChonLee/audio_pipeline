from config.secrets import FTP_PASS

FTP_LOCATIONS = {
    "srn": {
        "host": "192.168.7.150",
        #"host": "salemradionetwork.exavault.com",
        "user": "stevebrown",
        **FTP_PASS["srn"],
        "remote_dir": "/",
        #"files": ["H1.mp3", "S1_Sirius.wav", "S2_Sirius.wav"]  # files from processed folder
    },
    "ambos": {
        "host": "192.168.7.150",
        #"host": "ftp.ambassadoradvertising.com",
        "user": "KLProducer",
        **FTP_PASS["ambos"],
        "remote_dir": "/users/klproducer/Steve Brown Etc",
        # rename certain files when uploading
        #"files": ["H1.mp3"],
        #"rename": {"H1.mp3": "Show_Highlight.mp3"}
    },
    "kln": {
        "host": "192.168.7.150",
        #"host": "home215602109.1and1-data.host",
        "user": "acc1186603788",
        **FTP_PASS["kln"],
        "remote_dir": "/sbetc/steve-brown-etc-podcast",
        #"files": ["Podcast.mp3"]  # only upload the podcast
    }
}