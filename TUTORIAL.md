# **Trip Genius - Detailed Tutorial**

This tutorial provides step-by-step instructions for installing, configuring, and running the **Trip Genius** application. The setup covers both the backend (built using FastAPI) and the frontend (built using React), ensuring a seamless execution of the project.

---

## **1. Installation Instructions**

### Prerequisites
Ensure that you have the following tools installed:
- **Python 3.8+**
- **Node.js** (v14 or higher) and **npm** (Node Package Manager)
- **Virtual Environment** for Python
- **Uvicorn** (to run the FastAPI server)

---

### **Step 1: Clone the Repository**

Clone the Trip Genius repository to your local machine:
```bash
git clone https://github.com/rattandeep1998/trip-genius
cd trip-genius
```

---

### **Step 2: Set Up the Python Backend**

1. **Navigate to the Backend Folder**:  
   ```bash
   cd app
   ```

2. **Create a Python Virtual Environment**:  
   Run the following commands to create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:  
   Use the `requirements.txt` file located in the `/app` folder to install all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

### **Step 3: Create and Configure the `.env` File**

The application requires API keys for several platforms. Create a `.env` file in the root directory with the following keys:

```plaintext
AMADEUS_CLIENT_ID=your_amadeus_client_id
AMADEUS_CLIENT_SECRET=your_amadeus_client_secret
OPENAI_API_KEY=your_openai_api_key
LANGCHAIN_API_KEY=your_langchain_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
TAVILY_API_KEY=your_tavily_api_key
TRIPADVISOR_API_KEY=your_tripadvisor_api_key
GOOGLE_PLACES_API_KEY=your_google_places_api_key
```

- Replace `your_xxx_api_key` with the actual API keys obtained from each respective platform.

---

### **Step 4: Start the FastAPI Backend**

Navigate to the `app` directory and run the following command to start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

- This will start the backend at `http://127.0.0.1:8000`.

---

### **Step 5: Set Up the React Frontend**

1. **Navigate to the Frontend Directory**:  
   ```bash
   cd ui
   ```

2. **Install Dependencies**:  
   Run the following command to install all required dependencies (from `package.json`):
   ```bash
   npm install
   ```

3. **Start the Frontend**:  
   Run the following command to start the React development server:
   ```bash
   npm start
   ```

- The frontend will be available at `http://localhost:3000`.

---

## **2. Running the Application**

### Option 1: End-to-End Interactive Usage

1. Start the backend:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Start the frontend:
   ```bash
   npm start
   ```

3. Open the browser and go to `http://localhost:3000` to interact with the **Trip Genius** interface.

---

### Option 2: Running a Single Query from the Terminal

You can directly execute the application with a single sample query using the following command:
```bash
python -m app.core.trip_genius
```

- **Default Query** (modifiable in the script):  
   `"Book a flight from New Delhi to New York, departing on December 20, 2024, and returning on January 5, 2025."`

---

### Option 3: Running on the Entire Dataset

To run the application on an entire dataset and evaluate the results:
```bash
python -m app.core.trip_genius_on_dataset
```

**Note**: Running on the full dataset will consume significant API and LLM calls due to multiple queries being processed.

---

### Option 4: Load Testing

To simulate and evaluate system performance under load, use the following command:
```bash
python scripts/load_test.py
```

This will run multiple concurrent queries to test the backend's robustness and efficiency.

---

## **3. Troubleshooting Guide**

### **Backend Issues**

1. **Missing Dependencies**:  
   - Ensure that all dependencies are installed:  
     ```bash
     pip install -r app/requirements.txt
     ```
   - Install other missing dependencies (if any) using pip on the terminal in the virtual env.

2. **Missing `.env` File or API Keys**:  
   - Confirm that the `.env` file exists in the root directory and contains valid API keys.

3. **Port Conflicts**:  
   - If the backend port `8000` is already in use, specify a different port:  
     ```bash
     uvicorn app.main:app --port 8001 --reload
     ```

4. **CORS Errors**:  
   - Ensure CORS is properly configured in the backend for the frontend URL:  
     ```python
     app.add_middleware(
         CORSMiddleware,
         allow_origins=["http://localhost:3000"],
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
     ```

---

### **Frontend Issues**

1. **Dependencies Not Installed**:  
   - Ensure all React dependencies are installed:  
     ```bash
     npm install
     ```

2. **Port Conflicts**:  
   - If the frontend port `3000` is already in use, specify a new port:  
     ```bash
     npm start -- --port=3001
     ```

3. **Backend Not Running**:  
   - Verify that the FastAPI backend is running at `http://127.0.0.1:8000`.

4. **API Not Responding**:  
   - Check backend logs for errors or missing API keys.

---

### **General Issues**

1. **API Rate Limits**:  
   - If running on an entire dataset, ensure sufficient API quotas are available for OpenAI, Amadeus, or other providers.

2. **System Performance**:  
   - For large-scale queries, monitor system performance and resource usage. Use `load_test.py` for benchmarking.

3. **LLM Errors**:  
   - If responses are incorrect or incomplete, verify API settings and check the query format.

---

## **Conclusion**

By following this tutorial, you can successfully set up, configure, and run the **Trip Genius** application on your local machine. Whether running interactively, testing on a dataset, or performing load testing, this guide provides all the necessary steps and troubleshooting tips to ensure a smooth experience.

If you encounter any issues, feel free to refer to the troubleshooting guide or debug logs for further assistance.