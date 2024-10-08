from __future__ import division, print_function
import os
import numpy as np
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import tensorflow as tf
from flask_cors import CORS  # Import CORS

# Disable oneDNN custom operations and suppress TensorFlow logs
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Define the class labels for your custom model
class_labels = ['EarlyPreB', 'PreB', 'ProB', 'Benign']

# Define a Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)  # Add this line to enable CORS

# Define model paths
MODEL_PATHS = {
    'EfficientB0': 'models/EfficientB0.tflite',
    'EfficientNetB0': 'models/EfficientNetB0.tflite',
    'MobileNetV2': 'models/MobileNetV2.tflite',
    'NasNetMobile': 'models/NasNetMobile.tflite'
}

# Ensure the uploads directory exists
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to load the TFLite model and allocate tensors
def load_model(model_name):
    model_path = MODEL_PATHS.get(model_name)
    if model_path is None:
        raise ValueError(f"Model '{model_name}' not found.")
    interpreter = tf.lite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter

# Function to preprocess the image and predict the class using the TFLite model
def model_predict(img_path, interpreter):
    try:
        img = tf.keras.preprocessing.image.load_img(img_path, target_size=(224, 224))
        x = tf.keras.preprocessing.image.img_to_array(img)
        x = np.expand_dims(x, axis=0)  # Add batch dimension
        x = tf.keras.applications.mobilenet_v2.preprocess_input(x)

        interpreter.set_tensor(interpreter.get_input_details()[0]['index'], x)
        interpreter.invoke()

        preds = interpreter.get_tensor(interpreter.get_output_details()[0]['index'])
        return preds
    except Exception as e:
        print(f"Error during prediction: {str(e)}")
        return None

# API to get available models
@app.route('/api/models', methods=['GET'])
def get_models():
    return jsonify({"models": list(MODEL_PATHS.keys())}), 200

# API to handle image uploads and predictions
@app.route('/api/predictions', methods=['POST'])
def upload():
    if 'files' not in request.files:
        return jsonify({"error": "No file part."}), 400

    files = request.files.getlist('files')  # Get multiple files
    if len(files) == 0 or all(f.filename == '' for f in files):
        return jsonify({"error": "At least one image file is required."}), 400

    selected_model = request.form.get('model')
    if selected_model not in MODEL_PATHS:
        return jsonify({"error": "Invalid model selected."}), 400

    results = []
    interpreter = load_model(selected_model)  # Load the model once

    for f in files[:6]:  # Limit to a maximum of 6 images
        if f.filename == '':
            continue  # Skip empty files

        # Save the file to the uploads directory
        file_path = os.path.join(UPLOAD_FOLDER, secure_filename(f.filename))
        f.save(file_path)

        # Make a prediction using the uploaded image
        preds = model_predict(file_path, interpreter)

        if preds is None:
            results.append({"filename": f.filename, "error": "Prediction failed."})
            os.remove(file_path)  # Delete the file even if prediction failed
            continue

        # Get the index of the class with the highest probability
        pred_class_idx = np.argmax(preds, axis=1)[0]
        result = class_labels[pred_class_idx] if pred_class_idx < len(class_labels) else "Prediction index out of range."
        results.append({"filename": f.filename, "predicted_class": result})

        # Delete the file after processing
        os.remove(file_path)

    return jsonify({"results": results}), 200

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
