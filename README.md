# Simulated Control Room Environment for LoRa Transmission.

## Project Setup Instructions

Follow these steps to set up the project and configure it according to your requirements:

### **1. Clone the Repository**
To clone the repository, run the following command in your terminal:
```bash
git clone https://github.com/TechTo-Green/LoRa2Server.git
```

Navigate into the project directory:
```bash
cd TechTo-Green
```

---

### **2. Set Up a Virtual Environment**
Create a Python virtual environment to manage dependencies:
```bash
python -m venv venv
```

Activate the virtual environment:
- On Linux/macOS:
  ```bash
  source venv/bin/activate
  ```
- On Windows:
  ```bash
  venv\Scripts\activate.bat
  ```

---

### **3. Install Required Packages**
Install all necessary dependencies using `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

### **4. Update Configuration**
Modify the `API_URL` and `EXP_KEYS` in `helmet/views.py` to suit your specific requirements or upgrades.

1. Open the file `helmet/views.py` in your preferred text editor.
2. Locate the following lines:
   ```python
   API_URL = "your_api_url_here"
   EXP_KEYS = "your_exp_keys_here"
   ```
3. Replace `"your_api_url_here"` and `"your_exp_keys_here"` with the appropriate values for your setup.

Save and close the file after making the changes.

---

### **5. Run the Application**
Once everything is set up, you can start using the application. Follow any additional instructions specific to your project for running or testing.
