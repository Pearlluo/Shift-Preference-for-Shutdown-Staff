# Shift Preference for Shutdown Staff

This project is a web-based internal tool for managing shift preferences (DS / NS / ANY) for shutdown employees.

It integrates with OPMS API to:
- Retrieve employee data
- Allow users to select preferred shifts
- Write the selected shift back to OPMS

---

##  Features

- Search employee by full name
- Auto-fill Employee ID and Position
- Select shift (DS / NS / ANY)
- Submit multiple employees at once
- Write data back to OPMS via API
- Mobile-friendly interface

---

##  Tech Stack

- Python (Flask)
- HTML / CSS / JavaScript
- OPMS API
- Azure Web App (deployment)
- GitHub (version control)

---

##  Project Structure


.
├── app.py
├── requirements.txt
├── templates/
│ └── shift_form.html


---

##  Setup (Local)

### 1. Install dependencies

```bash
pip install -r requirements.txt
2. Set environment variables
OPMS_CLIENT_ID=your_client_id
OPMS_CLIENT_SECRET=your_secret
3. Run the app
python app.py
☁️ Deployment (Azure)
Runtime: Python 3.11
Startup Command:
gunicorn app:app
Environment Variables (Azure Configuration):
OPMS_CLIENT_ID
OPMS_CLIENT_SECRET
Notes
Do NOT upload .env to GitHub
Ensure correct API permissions in OPMS
Only valid shifts are accepted: DS, NS, ANY

Author
Pearl Luo
