import os
import subprocess
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# --- Configuration ---
# You must update this path to where your Audiveris executable is located.
# On Windows, it might be: 'C:/Program Files/Audiveris/bin/Audiveris.bat'
# On macOS, it might be: '/Applications/Audiveris.app/Contents/MacOS/Audiveris'
# On Linux, it might be: '/usr/bin/audiveris'
AUDIVERIS_PATH = 'C:/Program Files/Audiveris/bin/Audiveris.bat' 

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
CORS(app) # Enable Cross-Origin Resource Sharing

# --- Helper Functions ---
def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_folders():
    """Creates the necessary folders if they don't exist."""
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- API Routes ---
@app.route('/process', methods=['POST'])
def process_sheet_music():
    """
    Handles the file upload and processing with Audiveris.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        # Generate a unique ID for this conversion job
        job_id = str(uuid.uuid4())
        input_filename = file.filename
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
        
        # We'll save the output in a subdirectory named after the job_id
        output_dir = os.path.join(app.config['OUTPUT_FOLDER'], job_id)
        os.makedirs(output_dir, exist_ok=True)
        
        file.save(input_path)
        
        print(f"File saved to: {input_path}")
        print(f"Output will be in: {output_dir}")

        try:
            # --- Run Audiveris ---
            # This is the core command that runs the OMR engine.
            # -batch: Run in headless mode (no GUI).
            # -run: Perform all steps from loading to export.
            # -export: Export the final results.
            # -output: Specify the directory where results are saved.
            command = [
                AUDIVERIS_PATH,
                '-batch',
                '-run',
                input_path,
                '-export',
                '-output',
                output_dir
            ]
            
            print(f"Running command: {' '.join(command)}")
            
            # Using subprocess.run to execute the command
            result = subprocess.run(command, capture_output=True, text=True, check=True)

            print("Audiveris stdout:", result.stdout)
            print("Audiveris stderr:", result.stderr)

            # --- Prepare Response ---
            # Audiveris usually names the output file based on the input, but without the extension.
            base_name = os.path.splitext(input_filename)[0]
            
            # We assume these are the files Audiveris creates.
            # You might need to adjust these filenames if Audiveris names them differently.
            files = {
                'xml': f'/results/{job_id}/{base_name}.mxl', # Audiveris often creates compressed .mxl
                'midi': f'/results/{job_id}/{base_name}.mid',
                'musescore': f'/results/{job_id}/{base_name}.mscz' # This might not be a direct output, often it's the .mxl
            }

            return jsonify(files), 200

        except subprocess.CalledProcessError as e:
            print(f"Error running Audiveris: {e}")
            print("Stderr:", e.stderr)
            print("Stdout:", e.stdout)
            return jsonify({"error": "Failed to process the sheet music with Audiveris.", "details": e.stderr}), 500
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    else:
        return jsonify({"error": "File type not allowed"}), 400

@app.route('/results/<path:path>')
def send_result(path):
    """Serves the processed files from the output directory."""
    return send_from_directory(app.config['OUTPUT_FOLDER'], path)


# --- Main Execution ---
if __name__ == '__main__':
    create_folders()
    # Running on 0.0.0.0 makes it accessible from your local network
    app.run(host='0.0.0.0', port=5000, debug=True)
