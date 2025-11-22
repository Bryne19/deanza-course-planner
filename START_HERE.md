# 🚀 How to Start the Web App

## Quick Start

1. **Open Terminal** and navigate to the web_app folder:
   ```bash
   cd /Users/student/Downloads/Project/web_app
   ```

2. **Run the application**:
   ```bash
   python3 run.py
   ```

3. **Open your web browser** and go to:
   ```
   http://localhost:5001
   ```
   (Or whatever port number is shown in the terminal)

## What You Should See

When you run `python3 run.py`, you should see:
```
🚀 Starting Flask app on http://localhost:5001
   Press Ctrl+C to stop

 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://0.0.0.0:5001
```

Then open your browser to `http://localhost:5001`

## Troubleshooting

### "Port already in use" error?
The run script will automatically find a free port. Just use the port number it shows you.

### "Module not found" error?
Make sure you have Flask installed:
```bash
pip3 install flask
```

### "Permission denied" error?
Make sure you're in the web_app directory:
```bash
cd /Users/student/Downloads/Project/web_app
```

### App starts but browser shows error?
- Make sure you're using the exact URL shown in the terminal (usually `http://localhost:5001`)
- Try `http://127.0.0.1:5001` instead
- Check that no firewall is blocking the connection

### Still not working?
Check the terminal output for error messages and share them.

## Stopping the App

Press `Ctrl+C` in the terminal where the app is running.

