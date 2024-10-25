import streamlit as st
import datetime
import requests
import time
from dateutil import parser 
from datetime import datetime as dt, time as dtt


current_time = dt.now()
start_time = dtt(7,0)   # 7:00 AM
end_time = dtt(16, 0)    # 4:00 PM
#st.write(current_time)

# Function to check if the current day is a weekday (Monday=0, Sunday=6)
def is_weekday():
    return current_time.weekday() < 5  # Monday to Friday

# Function to check if the current time is within the allowed time range
def is_within_time_range():
    current_time_of_day = current_time.time()  # Get just the time part
    return start_time <= current_time_of_day <= end_time

# Check both conditions: it's a weekday and within the allowed time range
#if is_weekday() and is_within_time_range():
    # If conditions are met, set the page to refresh every 5 minutes (300 seconds)
    #st.markdown("""
    #    <meta http-equiv="refresh" content="60">
    #    """, unsafe_allow_html=True)
    

# OAuth2 Configuration
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
tenant = st.secrets["tenant"]
st_app_key = st.secrets["st_app_key"]
token_url = 'https://auth.servicetitan.io/connect/token'

# Parameterized tagTypeIds for Op levels
TAG_TYPE_IDS = {
    "Op_1": 38473266,  # "Op 1"
    "Op_2": 38474803,  # "Op 2"
    "Op_3": 38473267,  # "Op 3"
    "No_Op": 72  # "No Op"
}

# Function to get OAuth2 token
def get_oauth_token(client_id, client_secret, token_url):
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()  # Check if the request was successful    
    token_data = response.json()
    return token_data['access_token'], token_data['expires_in']

# Function to get the cached token or request a new one
def get_cached_token():
    # Check if token is already in session state and still valid
    if "token" in st.session_state and "token_expiration" in st.session_state:
        if time.time() < st.session_state.token_expiration:
            # Token is still valid, use it
            #token = get_oauth_token(client_id, client_secret, token_url)
            #return token
            return st.session_state.token
    
    # If no valid token, request a new one
    token, expires_in = get_oauth_token(client_id, client_secret, token_url)
    
    # Cache the token and expiration time
    st.session_state.token = token
    st.session_state.token_expiration = time.time() + expires_in - 60  # Subtract 60 seconds as buffer
    
    return token

# Function to fetch shifts from the API for the next 5 days
def fetch_shifts(startDate, endDate):
    shift_url = f'https://api.servicetitan.io/dispatch/v2/tenant/{tenant}/technician-shifts?startsOnOrAfter={startDate}&endsOnOrBefore={endDate}&shiftType=Normal&titleContains=Regular%20Shift'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    response = requests.get(shift_url, headers=headers)
    response.raise_for_status()
    return response.json()

# Function to fetch appointments from API for the next 5 days
def fetch_appointments(startDate, endDate):
    appointmentList_url = f'https://api.servicetitan.io/jpm/v2/tenant/{tenant}/appointments?startsOnOrAfter={startDate}&startsBefore={endDate}&pageSize=100'
    token = get_cached_token()  # Get the cached token or request a new one
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key  # Add ST-App-Key from secrets
    }
    response = requests.get(appointmentList_url, headers=headers)
    response.raise_for_status()  # Check if the request was successful
    return response.json()

# Function to fetch job details using jobId
def fetch_job_details(job_id):
    job_url = f'https://api.servicetitan.io/jpm/v2/tenant/{tenant}/jobs/{job_id}'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    response = requests.get(job_url, headers=headers)
    response.raise_for_status()
    return response.json()

# Function to fetch technician assignments for appointments
def fetch_appointment_assignments(appointment_ids):
    assignment_url = f'https://api.servicetitan.io/dispatch/v2/tenant/{tenant}/appointment-assignments?appointmentIds={",".join(map(str, appointment_ids))}'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    response = requests.get(assignment_url, headers=headers)
    response.raise_for_status()
    return response.json()

def map_technician_names(appointments_data):
    appointment_ids = [appointment['id'] for appointment in appointments_data.get('data', [])]
    technician_mapping = {}

    # Fetch assignments for the given appointment IDs
    if appointment_ids:
        assignments_data = fetch_appointment_assignments(appointment_ids)
        for assignment in assignments_data.get('data', []):
            technician_id = assignment['technicianId']
            technician_name = assignment['technicianName']
            technician_mapping[technician_id] = technician_name

    return technician_mapping

# Function to get the next valid weekday (skipping weekends)
def get_next_weekday(current_day, days_ahead):
    target_day = current_day
    while days_ahead > 0:
        target_day += datetime.timedelta(days=1)
        # Skip Saturday (5) and Sunday (6)
        if target_day.weekday() < 5:
            days_ahead -= 1
    return target_day

# Get current UTC date as the start date, and 5 days later as the end date
startDate = (datetime.datetime.now(datetime.timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ'))
endDate = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)).replace(hour=7, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')
# Function to match appointments to dates and increase the metric count based on job tag

# Update process_appointments to include technician assignments and metrics
def process_appointments(appointments_data, today, next_day, third_day):
    # Appointments are inside the 'data' key
    appointments = appointments_data.get('data', [])  # Extract appointments from 'data' key

    # Initialize metric counts for each day and each tag type, mapped to technicians
    metrics = {}
    appointment_ids = []

    # Collect all appointmentIds for fetching technician assignments later
    for appointment in appointments:
        appointment_ids.append(appointment['id'])

    # Fetch technician assignments for all appointments
    technician_assignments = fetch_appointment_assignments(appointment_ids)

    # Process each appointment
    for appointment in appointments:
        try:
            appointment_date = parser.parse(appointment['start']).date()
        except Exception as e:
            st.error(f"Error parsing date: {appointment['start']}, {e}")
            continue

        # Fetch the corresponding job details using jobId
        job_details = fetch_job_details(appointment['jobId'])

        # Get the assigned technician for the appointment
        assignment = next((a for a in technician_assignments['data'] if a['appointmentId'] == appointment['id']), None)
        if assignment:
            technician_name = assignment['technicianName']
        else:
            technician_name = "Unknown"

        # Initialize metrics for the technician if not already present
        if technician_name not in metrics:
            metrics[technician_name] = {
                "Op_1": {"today": 0, "next_day": 0, "third_day": 0},
                "Op_2": {"today": 0, "next_day": 0, "third_day": 0},
                "Op_3": {"today": 0, "next_day": 0, "third_day": 0},
                "No_Op": {"today": 0, "next_day": 0, "third_day": 0}
            }

        # Loop over the defined tag types (Op_1, Op_2, Op_3, No_Op)
        
        #st.write(TAG_TYPE_IDS.items())
        for op_level, tag_id in TAG_TYPE_IDS.items():
            if tag_id in job_details.get('tagTypeIds', []):
                # Match appointment date to today, next_day, or third_day
                
                if appointment_date == today:
                    metrics[technician_name][op_level]["today"] += 1
                
                elif appointment_date == next_day:
                    metrics[technician_name][op_level]["next_day"] += 1
                    
                elif appointment_date == third_day:
                    metrics[technician_name][op_level]["third_day"] += 1
                    

    return metrics


# Function to get the name of the next weekday
def get_next_weekday2(current_day, days_ahead):
    # Calculate the date after the specified number of days
    target_day = current_day + datetime.timedelta(days=days_ahead)
    return target_day.strftime("%A")

# Get today's date
#today = datetime.date.today()

# Set up the three day headers
#today_name = today.strftime("%A")
#next_day_name = get_next_weekday(today, 1)
#third_day_name = get_next_weekday(today, 4 - today.weekday()) if today.weekday() >= 5 else get_next_weekday(today, 2)


# Get today's date
today = datetime.date.today()

# Calculate the next valid weekdays (skipping weekends)
next_day = get_next_weekday(today, 1)
third_day = get_next_weekday(today, 2)

# Get the names of the days
today_name = today.strftime("%A")
next_day_name = next_day.strftime("%A")
third_day_name = third_day.strftime("%A")


# Main logic to fetch and process shifts
try:
    # Fetch shifts from API for the next 5 days
    shifts_data = fetch_shifts(startDate, endDate)


    # Filter shifts by day and technicianId
    technicians_today = []
    technicians_next_day = []
    technicians_third_day = []

    for shift in shifts_data.get('data', []):
        shift_date = parser.parse(shift['start']).date()
        if shift_date == today:
            technicians_today.append(shift['technicianId'])
        elif shift_date == next_day:
            technicians_next_day.append(shift['technicianId'])
        elif shift_date == third_day:
            technicians_third_day.append(shift['technicianId'])

    # Now, fetch appointments for the next 5 days
    appointments_data = fetch_appointments(startDate, endDate)

    # Create a mapping from technicianId to technicianName
    technician_mapping = map_technician_names(appointments_data)

     # Process appointments to count "Op 1," "Op 2," "Op 3," and "No Op"
    appointment_metrics = process_appointments(appointments_data, today, next_day, third_day)


except requests.RequestException as e:
    st.error(f"Failed to fetch shifts: {e}")
    technicians_today = technicians_next_day = technicians_third_day = []



col1, col2 = st.columns([4, 6])

with col1:
    st.title("🎈 3 Day Schedule")
with col2:
    # Display when the data was last updated (in the top right corner)
    st.write(f"Last Updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")





# Custom CSS for a horizontal metric layout and card styling
st.markdown("""
    <style>
    .card {
        background-color: #f2f2f2;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.4);
        margin: 10px;
        text-align: center;
        width: 100%;
        max-width: 100%; /* Allow the card to grow to the full width of the container */
        flex-grow: 1; /* Allow the cards to grow equally based on available space */
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px;
        border-radius: 10px;
        flex-grow: 1; /* Allow the metric container to grow based on available space */
    }
    .technician-label {
        font-size: 16px;
        font-weight: bold;
        text-align: left;
        flex: 2;        
        white-space: nowrap; /* Prevent line breaks */
    }
    .technician-header {
        font-size: 24px;
        font-weight: normal;
        text-align: center;
        flex: 2;        
        white-space: nowrap; /* Prevent line breaks */
    }
    .metric-header {
        font-size: 24px;
        font-weight: normal;  
        color: #333;
        text-align: center;
        flex: 0 0 15%; /* Allow the value to be 15% of the container */
        
    }
    .metric-value {
        font-size: 36px;
        font-weight: bold;  
        color: #333;
        text-align: center;
        flex: 0 0 15%; /* Allow the value to be 15% of the container */
        
    }
    
    </style>
    """, unsafe_allow_html=True)







# Layout using columns
col1, col2, col3 = st.columns([2, 2, 2])

# First column: Today shifts
with col1:
    card_content_today = """
        <div class="card">
            <div class="card-header">Today</div>
            <div class="card-body">
                <div class="metric-container ">
                    <div class="technician-header">Technician</div>
                    <div class="metric-header">Op 1</div>
                    <div class="metric-header">Op 2</div>
                    <div class="metric-header">Op 3</div>
                    <div class="metric-header">No Op</div>
                </div>
    """
    for technician in technicians_today:
        # Get technician name from the mapping
        technician_name = technician_mapping.get(technician, "Unknown Tech")
        
        card_content_today += f"""<div class="metric-container">
                <div class="technician-label">{technician_name}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_1', {}).get('today', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_2', {}).get('today', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_3', {}).get('today', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('No_Op', {}).get('today', 0)}</div>
            </div>
        """
    card_content_today += "</div></div>"
    
    # Render entire card content as one markdown block
    st.markdown(card_content_today, unsafe_allow_html=True)

# Second column: Next Day shifts
with col2:
    card_content_next_day = f"""
        <div class="card">
            <div class="card-header">{next_day_name}</div>
            <div class="card-body">
                <div class="metric-container ">
                    <div class="technician-header">Technician</div>
                    <div class="metric-header">Op 1</div>
                    <div class="metric-header">Op 2</div>
                    <div class="metric-header">Op 3</div>
                    <div class="metric-header">No Op</div>
                </div>
    """
    for technician in technicians_next_day:
         # Get technician name from the mapping
        technician_name = technician_mapping.get(technician, "Unknown Tech")
        card_content_next_day += f"""<div class="metric-container">
                <div class="technician-label">{technician_name}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_1', {}).get('next_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_2', {}).get('next_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_3', {}).get('next_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('No_Op', {}).get('next_day', 0)}</div>
            </div>
        """
    card_content_next_day += "</div></div>"
    
    # Render entire card content as one markdown block
    st.markdown(card_content_next_day, unsafe_allow_html=True)

# Third column: Next Weekday shifts
with col3:
    card_content_third_day = f"""<div class="card">
            <div class="card-header">{third_day_name}</div>
            <div class="card-body">
                <div class="metric-container ">
                    <div class="technician-header">Technician</div>
                    <div class="metric-header">Op 1</div>
                    <div class="metric-header">Op 2</div>
                    <div class="metric-header">Op 3</div>
                    <div class="metric-header">No Op</div>
                </div>
    """
    for technician in technicians_third_day:
         # Get technician name from the mapping
        technician_name = technician_mapping.get(technician, "Unknown Tech")
        card_content_third_day += f""" <div class="metric-container">
<div class="technician-label">{technician_name}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_1', {}).get('third_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_2', {}).get('third_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('Op_3', {}).get('third_day', 0)}</div>
                <div class="metric-value">{appointment_metrics.get(technician_name, {}).get('No_Op', {}).get('third_day', 0)}</div>
            </div>
        """
    card_content_third_day += "</div></div>"
    
    # Render entire card content as one markdown block
    st.markdown(card_content_third_day, unsafe_allow_html=True)
