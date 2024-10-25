import streamlit as st
import datetime
import requests
import time
from dateutil import parser
from pytz import timezone

# Arizona Timezone
arizona_tz = timezone('America/Phoenix')

# OAuth2 Configuration
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
tenant = st.secrets["tenant"]
st_app_key = st.secrets["st_app_key"]
token_url = 'https://auth.servicetitan.io/connect/token'

# Get the current time in Arizona timezone
now = datetime.datetime.now(arizona_tz)

# Define working hours (7 AM to 4 PM) in Arizona time
start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
end_time = now.replace(hour=16, minute=0, second=0, microsecond=0)


st.markdown(
    """
    <script>
    function reloadPage() {
        window.location.reload();
    }
    setTimeout(reloadPage, 300000);  // Refresh page every 5 minutes
    </script>
    """,
    unsafe_allow_html=True
)


# Parameterized tagTypeIds for Op levels
TAG_TYPE_IDS = {
    "L1_No_Op": 38473266,  # "L1 No Op"
    "L2_No_Op": 38474803,  # "L2 No Op"
    "L3_No_Op": 38473267,   # "L3 No Op"

    "L1_Op": 38473266,  # "L1  Op"
    "L2_Op": 38474803,  # "L2  Op"
    "L3_Op": 38473267   # "L3  Op"
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
    if "token" in st.session_state and "token_expiration" in st.session_state:
        if time.time() < st.session_state.token_expiration:
            return st.session_state.token
    
    token, expires_in = get_oauth_token(client_id, client_secret, token_url)
    st.session_state.token = token
    st.session_state.token_expiration = time.time() + expires_in - 60
    return token

# Function to fetch appointments from API for a specific day
def fetch_appointments_by_day(start_datetime_utc, end_datetime_utc):
    appointmentList_url = f'https://api.servicetitan.io/jpm/v2/tenant/{tenant}/appointments?startsOnOrAfter={start_datetime_utc}&startsBefore={end_datetime_utc}'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    response = requests.get(appointmentList_url, headers=headers)
    response.raise_for_status()
    appointments_data = response.json()
    
    if 'data' not in appointments_data or not appointments_data.get('data', []):
        #st.write(f"No appointments found for {start_datetime_utc} to {end_datetime_utc}")
        return []
    
    
    return appointments_data.get('data', [])

# Function to fetch job details using bulk job IDs (up to 50 at a time)
def fetch_job_details_bulk(job_ids):
    if not job_ids:
        st.write("No job IDs to fetch.")
        return {}

    job_url = f'https://api.servicetitan.io/jpm/v2/tenant/{tenant}/jobs?ids={",".join(job_ids)}'
    token = get_cached_token()
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key
    }
    
    response = requests.get(job_url, headers=headers)
    response.raise_for_status()
    job_details_data = response.json()

    
    return {job['id']: job for job in job_details_data.get('data', [])}

# Function to process appointments for a given day
def process_appointments_by_day(start_datetime_utc, end_datetime_utc):
    appointments = fetch_appointments_by_day(start_datetime_utc, end_datetime_utc)
    
    if not appointments:
        return (0, 0, 0, 0, 0, 0)  # Return zeros if no appointments

    # Get job IDs from the appointments (max 50)
    job_ids = [str(appointment['jobId']) for appointment in appointments[:50]]
    
    # Fetch job details for those job IDs in bulk
    job_details_dict = fetch_job_details_bulk(job_ids)



    # Initialize metric counts for Op and No Op
    metric_L1_No_Op = 0
    metric_L2_No_Op = 0
    metric_L3_No_Op = 0
    metric_L1_Op = 0
    metric_L2_Op = 0
    metric_L3_Op = 0

    # Process each appointment and update the Op/No Op metrics
    for appointment in appointments:
        job_id = appointment['jobId']
        job_details = job_details_dict.get(job_id, {})

        if TAG_TYPE_IDS["L1_No_Op"] in job_details.get('tagTypeIds', []):
            metric_L1_No_Op += 1

        if TAG_TYPE_IDS["L2_No_Op"] in job_details.get('tagTypeIds', []):
            metric_L2_No_Op += 1

        if TAG_TYPE_IDS["L3_No_Op"] in job_details.get('tagTypeIds', []):
            metric_L3_No_Op += 1

        if TAG_TYPE_IDS["L1_Op"] in job_details.get('tagTypeIds', []):
            metric_L1_Op += 1

        if TAG_TYPE_IDS["L2_Op"] in job_details.get('tagTypeIds', []):
            metric_L2_Op += 1

        if TAG_TYPE_IDS["L3_Op"] in job_details.get('tagTypeIds', []):
            metric_L3_Op += 1

    return (metric_L1_No_Op, metric_L2_No_Op, metric_L3_No_Op,
            metric_L1_Op, metric_L2_Op, metric_L3_Op)

# Convert Arizona time to UTC time
def convert_to_utc(dt_arizona):
    dt_utc = dt_arizona.astimezone(datetime.timezone.utc)
    return dt_utc

# Function to format datetime for API
def format_datetime(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

# Function to get the next valid weekday (skipping weekends)
def get_next_weekday(current_day, days_ahead):
    target_day = current_day
    while days_ahead > 0:
        target_day += datetime.timedelta(days=1)
        if target_day.weekday() < 5:
            days_ahead -= 1
    return target_day

# Get today's date and calculate the next two weekdays
today = datetime.date.today()
next_day = get_next_weekday(today, 1)
third_day = get_next_weekday(today, 2)

# Define the start and end datetime for each day in Arizona time
today_start_az = datetime.datetime.combine(today, datetime.time(0, 0)).replace(tzinfo=arizona_tz)
today_end_az = datetime.datetime.combine(today, datetime.time(23, 59)).replace(tzinfo=arizona_tz)

next_day_start_az = datetime.datetime.combine(next_day, datetime.time(0, 0)).replace(tzinfo=arizona_tz)
next_day_end_az = datetime.datetime.combine(next_day, datetime.time(23, 59)).replace(tzinfo=arizona_tz)

third_day_start_az = datetime.datetime.combine(third_day, datetime.time(0, 0)).replace(tzinfo=arizona_tz)
third_day_end_az = datetime.datetime.combine(third_day, datetime.time(23, 59)).replace(tzinfo=arizona_tz)

# Convert Arizona time to UTC time for the API
today_start_utc = convert_to_utc(today_start_az)
today_end_utc = convert_to_utc(today_end_az)

next_day_start_utc = convert_to_utc(next_day_start_az)
next_day_end_utc = convert_to_utc(next_day_end_az)

third_day_start_utc = convert_to_utc(third_day_start_az)
third_day_end_utc = convert_to_utc(third_day_end_az)

# Process appointments and job details for each day (for both Op and No Op metrics)
try:
    (metric_L1_No_Op_today, metric_L2_No_Op_today, metric_L3_No_Op_today,
     metric_L1_Op_today, metric_L2_Op_today, metric_L3_Op_today) = process_appointments_by_day(
        format_datetime(today_start_utc), format_datetime(today_end_utc))
    
    (metric_L1_No_Op_next_day, metric_L2_No_Op_next_day, metric_L3_No_Op_next_day,
     metric_L1_Op_next_day, metric_L2_Op_next_day, metric_L3_Op_next_day) = process_appointments_by_day(
        format_datetime(next_day_start_utc), format_datetime(next_day_end_utc))
    
    (metric_L1_No_Op_third_day, metric_L2_No_Op_third_day, metric_L3_No_Op_third_day,
     metric_L1_Op_third_day, metric_L2_Op_third_day, metric_L3_Op_third_day) = process_appointments_by_day(
        format_datetime(third_day_start_utc), format_datetime(third_day_end_utc))
except requests.RequestException as e:
    st.error(f"Failed to fetch data: {e}")
    metric_L1_No_Op_today = metric_L1_No_Op_next_day = metric_L1_No_Op_third_day = 0
    metric_L2_No_Op_today = metric_L2_No_Op_next_day = metric_L2_No_Op_third_day = 0
    metric_L3_No_Op_today = metric_L3_No_Op_next_day = metric_L3_No_Op_third_day = 0
    metric_L1_Op_today = metric_L1_Op_next_day = metric_L1_Op_third_day = 0
    metric_L2_Op_today = metric_L2_Op_next_day = metric_L2_Op_third_day = 0
    metric_L3_Op_today = metric_L3_Op_next_day = metric_L3_Op_third_day = 0



# Add targets for Op and No Op metrics
target_L1_No_Op = 3
target_L2_No_Op = 2
target_L3_No_Op = 1
target_L1_Op = 9
target_L2_Op = 6
target_L3_Op = 2


# Calculate deltas for Op and No Op for each day
delta_L1_No_Op_today = target_L1_No_Op - metric_L1_No_Op_today
delta_L2_No_Op_today = target_L2_No_Op - metric_L2_No_Op_today
delta_L3_No_Op_today = target_L3_No_Op - metric_L3_No_Op_today
delta_L1_Op_today = target_L1_Op - metric_L1_Op_today
delta_L2_Op_today = target_L2_Op - metric_L2_Op_today
delta_L3_Op_today = target_L3_Op - metric_L3_Op_today

# Similar for next day and third day...
# Next day deltas
delta_L1_No_Op_next_day = target_L1_No_Op - metric_L1_No_Op_next_day
delta_L2_No_Op_next_day = target_L2_No_Op - metric_L2_No_Op_next_day
delta_L3_No_Op_next_day = target_L3_No_Op - metric_L3_No_Op_next_day
delta_L1_Op_next_day = target_L1_Op - metric_L1_Op_next_day
delta_L2_Op_next_day = target_L2_Op - metric_L2_Op_next_day
delta_L3_Op_next_day = target_L3_Op - metric_L3_Op_next_day

# Third day deltas
delta_L1_No_Op_third_day = target_L1_No_Op - metric_L1_No_Op_third_day
delta_L2_No_Op_third_day = target_L2_No_Op - metric_L2_No_Op_third_day
delta_L3_No_Op_third_day = target_L3_No_Op - metric_L3_No_Op_third_day
delta_L1_Op_third_day = target_L1_Op - metric_L1_Op_third_day
delta_L2_Op_third_day = target_L2_Op - metric_L2_Op_third_day
delta_L3_Op_third_day = target_L3_Op - metric_L3_Op_third_day

# Get the names of the days
today_name = today.strftime("%A")
next_day_name = next_day.strftime("%A")
third_day_name = third_day.strftime("%A")

# Determine colors for delta (red for negative, green for positive or zero)
def get_delta_color(delta):
    return "negative" if delta < 0 else "positive"

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
        max-width: 100%;
        flex-grow: 1;
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px;
        border-radius: 10px;
        flex-grow: 1;
    }
    .metric-label {
        font-size: 24px;
        font-weight: bold;
        text-align: left;
        flex: 1;
    }
    .label-header {
        font-size: 24px;
        font-weight: normal;
        text-align: center;
        flex: 1;
    }
    .metric-value {
        font-size: 36px;
        font-weight: bold;
        color: #333;
        text-align: center;
        flex: 1;
    }
    .metric-header {
        font-size: 24px;
        font-weight: normal;
        color: #333;
        text-align: center;
        flex: 1;
    }
    .metric-delta {
        position: relative;
        font-size: 16px;
        font-weight: bold;
        text-align: right;
        flex: 0 0 10%;
        top: -10px;
        left: 5px;
    }
    .metric-delta.negative {
        color: red;
    }
    .metric-delta.positive {
        color: green;
    }
    /* CSS to align Last Updated text with title */
    .title-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }
    .title {
        font-size: 32px;
        font-weight: bold;
    }
    .last-updated {
        font-size: 16px;
        text-align: right;
        padding-right: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Layout with title and Last Updated message
col1, col2 = st.columns([4, 6])
with col1:
    st.markdown('<div class="title">🎈 3 Day Schedule</div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="last-updated">Last Updated: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}</div>', unsafe_allow_html=True)


# Layout using columns
col1, col2, col3 = st.columns([2, 2, 2])

# First column: Today
with col1:
    st.markdown(f"""
        <div class="card">Today
            <div class="metric-container ">
                <div class="label-header">Level</div>
                <div class="metric-header">Op</div>
                <div class="metric-header">No Op</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 1</div>
                <div class="metric-value">{metric_L1_Op_today}<span class="metric-delta {get_delta_color(delta_L1_Op_today)}">{delta_L1_Op_today}</span></div>
                <div class="metric-value">{metric_L1_No_Op_today}<span class="metric-delta {get_delta_color(delta_L1_No_Op_today)}">{delta_L1_No_Op_today}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 2</div>
                <div class="metric-value">{metric_L2_Op_today}<span class="metric-delta {get_delta_color(delta_L2_Op_today)}">{delta_L2_Op_today}</span></div>
                <div class="metric-value">{metric_L2_No_Op_today}<span class="metric-delta {get_delta_color(delta_L2_No_Op_today)}">{delta_L2_No_Op_today}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 3</div>
                <div class="metric-value">{metric_L3_Op_today}<span class="metric-delta {get_delta_color(delta_L3_Op_today)}">{delta_L3_Op_today}</span></div>
                <div class="metric-value">{metric_L3_No_Op_today}<span class="metric-delta {get_delta_color(delta_L3_No_Op_today)}">{delta_L3_No_Op_today}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Second column: Next Day
with col2:
    st.markdown(f"""
        <div class="card">{next_day_name}
            <div class="metric-container ">
                <div class="label-header">Level</div>
                <div class="metric-header">Op</div>
                <div class="metric-header">No Op</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 1</div>
                <div class="metric-value">{metric_L1_Op_next_day}<span class="metric-delta {get_delta_color(delta_L1_Op_next_day)}">{delta_L1_Op_next_day}</span></div>
                <div class="metric-value">{metric_L1_No_Op_next_day}<span class="metric-delta {get_delta_color(delta_L1_No_Op_next_day)}">{delta_L1_No_Op_next_day}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 2</div>
                <div class="metric-value">{metric_L2_Op_next_day}<span class="metric-delta {get_delta_color(delta_L2_Op_next_day)}">{delta_L2_Op_next_day}</span></div>
                <div class="metric-value">{metric_L2_No_Op_next_day}<span class="metric-delta {get_delta_color(delta_L2_No_Op_next_day)}">{delta_L2_No_Op_next_day}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 3</div>
                <div class="metric-value">{metric_L3_Op_next_day}<span class="metric-delta {get_delta_color(delta_L3_Op_next_day)}">{delta_L3_Op_next_day}</span></div>
                <div class="metric-value">{metric_L3_No_Op_next_day}<span class="metric-delta {get_delta_color(delta_L3_No_Op_next_day)}">{delta_L3_No_Op_next_day}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Third column: Third Day
with col3:
    st.markdown(f"""
        <div class="card">{third_day_name}
            <div class="metric-container ">
                <div class="label-header">Level</div>
                <div class="metric-header">Op</div>
                <div class="metric-header">No Op</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 1</div>
                <div class="metric-value">{metric_L1_Op_third_day}<span class="metric-delta {get_delta_color(delta_L1_Op_third_day)}">{delta_L1_Op_third_day}</span></div>
                <div class="metric-value">{metric_L1_No_Op_third_day}<span class="metric-delta {get_delta_color(delta_L1_No_Op_third_day)}">{delta_L1_No_Op_third_day}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 2</div>
                <div class="metric-value">{metric_L2_Op_third_day}<span class="metric-delta {get_delta_color(delta_L2_Op_third_day)}">{delta_L2_Op_third_day}</span></div>
                <div class="metric-value">{metric_L2_No_Op_third_day}<span class="metric-delta {get_delta_color(delta_L2_No_Op_third_day)}">{delta_L2_No_Op_third_day}</span></div>
            </div>
            <div class="metric-container">
                <div class="metric-label">Level 3</div>
                <div class="metric-value">{metric_L3_Op_third_day}<span class="metric-delta {get_delta_color(delta_L3_Op_third_day)}">{delta_L3_Op_third_day}</span></div>
                <div class="metric-value">{metric_L3_No_Op_third_day}<span class="metric-delta {get_delta_color(delta_L3_No_Op_third_day)}">{delta_L3_No_Op_third_day}</span></div>
            </div>
        </div>
    """, unsafe_allow_html=True)



# Check if current time is within working hours and it's a weekday (Mon-Fri)
if now.weekday() < 5 and start_time <= now <= end_time:
    # Add JavaScript to automatically refresh the page every 5 minutes (300000 milliseconds)
    st.markdown(
        """
        <script>
        function reloadPage() {
            window.location.reload();
        }
        setTimeout(reloadPage, 300000);  // Refresh page every 5 minutes
        </script>
        """,
        unsafe_allow_html=True
    )
    st.write("Page will refresh every 5 minutes between 7 AM and 4 PM on weekdays.")
else:
    st.write("Outside of working hours, the page will not refresh.")

