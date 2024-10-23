import streamlit as st
import datetime
import requests
import time

# OAuth2 Configuration
client_id = st.secrets["client_id"]
client_secret = st.secrets["client_secret"]
tenant = st.secrets["tenant"]
#st_app_key = st.secrets["st_app_key"]
token_url = 'https://auth-integration.servicetitan.io/connect/token'
appointmentList_url = f'https://api-integration.servicetitan.io/jpm/v2/tenant/{tenant}/appointments?startsOnOrAfter=2022-03-01T14:00:00Z&status=Scheduled,Dispatched,Working'


st.write(st.secrets)


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


# Function to fetch metric data from the API
def fetch_data(url):
    token = get_cached_token()  # Get the cached token or request a new one
    headers = {
        'Authorization': f'Bearer {token}'
    }
    # Set headers for the request (OAuth2 token and ST-App-Key)
    headers = {
        'Authorization': f'Bearer {token}',
        'ST-App-Key': st_app_key  # Add ST-App-Key from secrets
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Check if the request was successful
    return response.json()

# Function to get the name of the next weekday
def get_next_weekday(current_day, days_ahead):
    # Calculate the date after the specified number of days
    target_day = current_day + datetime.timedelta(days=days_ahead)
    return target_day.strftime("%A")

# Get today's date
today = datetime.date.today()

# Set up the three day headers
today_name = today.strftime("%A")
next_day_name = get_next_weekday(today, 1)
third_day_name = get_next_weekday(today, 4 - today.weekday()) if today.weekday() >= 5 else get_next_weekday(today, 2)



# Get OAuth2 token
try:
    
    # Fetch metric data from API
    metrics_data = fetch_data(appointmentList_url)
    # Example: extracting values from the API response
    metric_L3_No_Op_today = metrics_data['today']['L3_No_Op']
    metric_L2_No_Op_today = metrics_data['today']['L2_No_Op']
    metric_L3_No_Op_2nd_Day = metrics_data['next_day']['L3_No_Op']
    metric_L2_No_Op_2nd_Day = metrics_data['next_day']['L2_No_Op']
    metric_L3_No_Op_3rd_Day = metrics_data['third_day']['L3_No_Op']
    metric_L2_No_Op_3rd_Day = metrics_data['third_day']['L2_No_Op']
except requests.RequestException as e:
    st.error(f"Failed to fetch metrics: {e}")
    metric_L3_No_Op_today = 0  # Fallback to default value
    metric_L2_No_Op_today = 0
    metric_L3_No_Op_2nd_Day = 0
    metric_L2_No_Op_2nd_Day = 0
    metric_L3_No_Op_3rd_Day = 0
    metric_L2_No_Op_3rd_Day = 0




# Targets for each label
target_L3_No_Op = 3
target_L2_No_Op = 5


# Calculate deltas for today
delta_L3_No_Op_today = target_L3_No_Op - metric_L3_No_Op_today
delta_L2_No_Op_today = target_L2_No_Op - metric_L2_No_Op_today

# Calculate deltas for the second day
delta_L3_No_Op_2nd_Day = target_L3_No_Op - metric_L3_No_Op_2nd_Day
delta_L2_No_Op_2nd_Day = target_L2_No_Op - metric_L2_No_Op_2nd_Day

# Calculate deltas for the third day
delta_L3_No_Op_3rd_Day = target_L3_No_Op - metric_L3_No_Op_3rd_Day
delta_L2_No_Op_3rd_Day = target_L2_No_Op - metric_L2_No_Op_3rd_Day

# Determine colors for delta (red for negative, green for positive or zero)
def get_delta_color(delta):
    return "negative" if delta < 0 else "positive"


st.title("🎈 3 Day Schedule")


# Custom CSS for a horizontal metric layout and card styling
st.markdown("""
    <style>
    .card {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.1);
        margin: 10px;
        text-align: center;
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px;
        border-radius: 10px;
    }
    .metric-label {
        font-size: 16px;
        font-weight: bold;
        text-align: left;
        
        #flex: 1;
        width: 70%; /* Set width for the label */
        white-space: nowrap; /* Prevent line breaks */
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;  
        color: #333;
        text-align: right;
        #flex: 1;
        width: 15%;
        
    }
    .metric-delta {
        font-size: 16px;
        font-weight: bold;
        text-align: right;
        width: 15%;
        #flex: 1;
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
col1, col2, col3 = st.columns(3)

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
                <div class="metric-value">{metric_L3_No_Op_2nd_Day}</div>
                <div class="metric-delta {get_delta_color(delta_L3_No_Op_2nd_Day)}">{delta_L3_No_Op_2nd_Day}</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">L2 No Op</div>
                <div class="metric-value">{metric_L2_No_Op_2nd_Day}</div>
                <div class="metric-delta {get_delta_color(delta_L2_No_Op_2nd_Day)}">{delta_L2_No_Op_2nd_Day}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# Third column: Next Weekday (L3 No Op and L2 No Op)
with col3:
    st.markdown(f"""
        <div class="card">{third_day_name}
            <div class="metric-container">
                <div class="metric-label">L3 No Op</div>
                <div class="metric-value">{metric_L3_No_Op_3rd_Day}</div>
                <div class="metric-delta {get_delta_color(delta_L3_No_Op_3rd_Day)}">{delta_L3_No_Op_3rd_Day}</div>
            </div>
            <div class="metric-container">
                <div class="metric-label">L2 No Op</div>
                <div class="metric-value">{metric_L2_No_Op_3rd_Day}</div>
                <div class="metric-delta {get_delta_color(delta_L2_No_Op_3rd_Day)}">{delta_L2_No_Op_3rd_Day}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)