import streamlit as st
import datetime
import requests
import time
from dateutil import parser 

# OAuth2 Configuration
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
tenant = st.secrets["tenant"]
st_app_key = st.secrets["st_app_key"]
token_url = 'https://auth-integration.servicetitan.io/connect/token'

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
             return st.session_state.token
    
    # If no valid token, request a new one
    token, expires_in = get_oauth_token(client_id, client_secret, token_url)
    
    # Cache the token and expiration time
    st.session_state.token = token
    st.session_state.token_expiration = time.time() + expires_in - 60  # Subtract 60 seconds as buffer
    
    return token

# Function to fetch appointments from API
def fetch_appointments():
    appointmentList_url = f'https://api-integration.servicetitan.io/jpm/v2/tenant/{tenant}/appointments?startsOnOrAfter=2022-03-01T14:00:00Z&status=Scheduled,Dispatched,Working'
    token = get_cached_token()  # Get the cached token or request a new one
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key  # Add ST-App-Key from secrets
    }
    response = requests.get(appointmentList_url, headers=headers)
    response.raise_for_status()
    return response.json()

# Function to fetch job details using jobId
def fetch_job_details(job_id):
    job_url = f'https://api-integration.servicetitan.io/jpm/v2/tenant/{tenant}/jobs/{job_id}'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    response = requests.get(job_url, headers=headers)
    response.raise_for_status()
    return response.json()

# Function to get the next valid weekday (skipping weekends)
def get_next_weekday(current_day, days_ahead):
    target_day = current_day
    while days_ahead > 0:
        target_day += datetime.timedelta(days=1)
        # Skip Saturday (5) and Sunday (6)
        if target_day.weekday() < 5:
            days_ahead -= 1
    return target_day

# Function to match appointments to dates and increase the metric count based on job tag
def process_appointments(appointments_data, today, next_day, third_day):
    # Appointments are inside the 'data' key
    appointments = appointments_data.get('data', [])  # Extract appointments from 'data' key

    # Initialize metric counts for each day
    metric_L3_No_Op_today = 0
    metric_L3_No_Op_next_day = 0
    metric_L3_No_Op_third_day = 0
    metric_L2_No_Op_today = 0
    metric_L2_No_Op_next_day = 0
    metric_L2_No_Op_third_day = 0

    for appointment in appointments:
        # Convert appointment start time to a date
        try:
            appointment_date = parser.parse(appointment['start']).date()
        except Exception as e:
            st.error(f"Error parsing date: {appointment['start']}, {e}")
            continue

        # Fetch the corresponding job details using jobId
        job_details = fetch_job_details(appointment['jobId'])

        # Check if the job contains the tagTypeId 69 (L3 No Op) or 70 (L2 No Op)
        if 69 in job_details.get('tagTypeIds', []):
            # Match appointment date to today, next_day, or third_day
            if appointment_date == today:
                metric_L3_No_Op_today += 1
            elif appointment_date == next_day:
                metric_L3_No_Op_next_day += 1
            elif appointment_date == third_day:
                metric_L3_No_Op_third_day += 1
        
        if 70 in job_details.get('tagTypeIds', []):  # Assuming 70 is L2 No Op
            if appointment_date == today:
                metric_L2_No_Op_today += 1
            elif appointment_date == next_day:
                metric_L2_No_Op_next_day += 1
            elif appointment_date == third_day:
                metric_L2_No_Op_third_day += 1

    return (metric_L3_No_Op_today, metric_L3_No_Op_next_day, metric_L3_No_Op_third_day,
            metric_L2_No_Op_today, metric_L2_No_Op_next_day, metric_L2_No_Op_third_day)



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

# Main logic to fetch and process appointments
try:
    # Fetch appointments from API
    appointments_data = fetch_appointments()

    # Process appointments to count metrics for today, next weekday, and third weekday
    (metric_L3_No_Op_today, metric_L3_No_Op_next_day, metric_L3_No_Op_third_day,
     metric_L2_No_Op_today, metric_L2_No_Op_next_day, metric_L2_No_Op_third_day) = process_appointments(
        appointments_data, today, next_day, third_day)

except requests.RequestException as e:
    st.error(f"Failed to fetch data: {e}")
    metric_L3_No_Op_today = metric_L3_No_Op_next_day = metric_L3_No_Op_third_day = 0
    metric_L2_No_Op_today = metric_L2_No_Op_next_day = metric_L2_No_Op_third_day = 0

# Targets for each label
target_L3_No_Op = 3
target_L2_No_Op = 5

# Calculate deltas for today
delta_L3_No_Op_today = target_L3_No_Op - metric_L3_No_Op_today
delta_L2_No_Op_today = target_L2_No_Op - metric_L2_No_Op_today

# Calculate deltas for the next day
delta_L3_No_Op_next_day = target_L3_No_Op - metric_L3_No_Op_next_day
delta_L2_No_Op_next_day = target_L2_No_Op - metric_L2_No_Op_next_day

# Calculate deltas for the third day
delta_L3_No_Op_third_day = target_L3_No_Op - metric_L3_No_Op_third_day
delta_L2_No_Op_third_day = target_L2_No_Op - metric_L2_No_Op_third_day

# Determine colors for delta (red for negative, green for positive or zero)
def get_delta_color(delta):
    return "negative" if delta < 0 else "positive"


st.title("🎈 3 Day Schedule")


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
    .metric-label {
        font-size: 24px;
        font-weight: bold;
        text-align: left;
        flex: 2;        
        white-space: nowrap; /* Prevent line breaks */
    }
    .metric-value {
        font-size: 36px;
        font-weight: bold;  
        color: #333;
        text-align: right;
        flex: 0 0 20%; /* Allow the value to be 15% of the container */
        
    }
    .metric-delta {
        font-size: 16px;
        font-weight: bold;
        text-align: right;        
        flex: 0 0 10%; /* Allow the value to be 15% of the container */
    }
    .metric-delta.negative {
        color: red; /* For failure */
    }
    .metric-delta.positive {
        color: green; /* For success */
    }
    </style>
    """, unsafe_allow_html=True)

# Layout using columns
col1, col2, col3 = st.columns([2,2,2])

# First column: Today (L3 No Op and L2 No Op)
with col1:
    st.markdown(f"""
        <div class="card">Today
            <div class="metric-container">
                <div class="metric-label">L3 No Op</div>
                <div class="metric-value">{metric_L3_No_Op_today}</div>
                <div class="metric-delta {get_delta_color(delta_L3_No_Op_today)}">{delta_L3_No_Op_today}</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">L2 No Op</div>
                <div class="metric-value">{metric_L2_No_Op_today}</div>
                <div class="metric-delta {get_delta_color(delta_L2_No_Op_today)}">{delta_L2_No_Op_today}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Second column: Next Day (L3 No Op and L2 No Op)
with col2:
    st.markdown(f"""
        <div class="card">{next_day_name}
            <div class="metric-container">
                <div class="metric-label">L3 No Op</div>
                <div class="metric-value">{metric_L3_No_Op_next_day}</div>
                <div class="metric-delta {get_delta_color(delta_L3_No_Op_next_day)}">{delta_L3_No_Op_next_day}</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">L2 No Op</div>
                <div class="metric-value">{metric_L2_No_Op_next_day}</div>
                <div class="metric-delta {get_delta_color(delta_L2_No_Op_next_day)}">{delta_L2_No_Op_next_day}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Third column: Next Weekday (L3 No Op and L2 No Op)
with col3:
    st.markdown(f"""
        <div class="card">{third_day_name}
            <div class="metric-container">
                <div class="metric-label">L3 No Op</div>
                <div class="metric-value">{metric_L3_No_Op_third_day}</div>
                <div class="metric-delta {get_delta_color(delta_L3_No_Op_third_day)}">{delta_L3_No_Op_third_day}</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">L2 No Op</div>
                <div class="metric-value">{metric_L2_No_Op_third_day}</div>
                <div class="metric-delta {get_delta_color(delta_L2_No_Op_third_day)}">{delta_L2_No_Op_third_day}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)