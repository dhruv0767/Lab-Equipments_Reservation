import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import datetime
import plotly.express as px
import json
from io import StringIO
import os, time
import subprocess

st.set_page_config(layout="wide")

# Set the timezone
os.environ['TZ'] = 'Asia/Bangkok'
time.tzset()

# Constants
PCR_FILE_PATH = 'pcr_data.csv'
NON_PCR_FILE_PATH = 'non_pcr_data.csv'
ANNOUNCEMENT_FILE_PATH = 'announcement.txt'
AUTOCLAVES_PATH = 'autoclaves_count.csv'
LOG_FILE_PATH = "change_log.csv"
EQUIPMENT_DETAILS_FILE_PATH = 'equipment_details.json'

# Initialize files if they don't exist
def init_file(file_path, columns=None):
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=columns) if columns else pd.DataFrame()
        df.to_csv(file_path, index=False)

def init_announcement_file():
    if not os.path.exists(ANNOUNCEMENT_FILE_PATH):
        with open(ANNOUNCEMENT_FILE_PATH, 'w') as f:
            f.write('')

# Call initialization functions
init_file(PCR_FILE_PATH, ['Name', 'Room', 'Equipments', 'Start_Time', 'End_Time'])
init_file(NON_PCR_FILE_PATH, ['Name', 'Room', 'Equipments', 'Start_Time', 'End_Time'])
init_file(AUTOCLAVES_PATH, ['Counts'])
init_announcement_file()

# Read the announcement from the text file
def read_announcement():
    if os.path.exists(ANNOUNCEMENT_FILE_PATH):
        with open(ANNOUNCEMENT_FILE_PATH, 'r') as f:
            announcement = f.read().strip()
        return announcement
    return ''

# Update the announcement in the text file
def update_announcement(text, file_path=ANNOUNCEMENT_FILE_PATH):
    try:
        with open(file_path, 'w') as file:
            file.write(text)
        backup_to_github(file_path, commit_message="Update announcements")
    except Exception as e:
        st.error(f"Error saving announcement: {e}")

# Load data from CSV
def load_data(file_path):
    try:
        if os.path.exists(file_path):
            return pd.read_csv(file_path)
        return pd.DataFrame(columns=['Equipments', 'Start_Time', 'End_Time', 'Name'])  # Return an empty DataFrame if the file does not exist
    except Exception as e:
        st.error(f"Error reading data from file {file_path}: {e}")
        return pd.DataFrame()

# Save data to CSV
def save_data(df, file_path):
    try:
        df.to_csv(file_path, index=False)
        backup_to_github(file_path, commit_message=f"Update {os.path.basename(file_path)}")
    except Exception as e:
        st.error(f"Error saving data: {e}")

def fetch_data(file_path):
    df = load_data(file_path)
    df['Start_Time'] = pd.to_datetime(df['Start_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')
    df['End_Time'] = pd.to_datetime(df['End_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')
    return df

# Configure Git
def configure_git():
    try:
        username = st.secrets["github"]["username"]
        email = st.secrets["github"]["email"]
        subprocess.run(["git", "config", "--global", "user.name", username], check=True)
        subprocess.run(["git", "config", "--global", "user.email", email], check=True)
    except subprocess.CalledProcessError as e:
        st.error(f"An error occurred while configuring Git: {e}")

# Backup to GitHub
def backup_to_github(file_path, commit_message="Update data"):
    try:
        configure_git()
        username = st.secrets["github"]["username"]
        token = st.secrets["github"]["token"]

        # Set up the remote URL with the token for authentication
        repo_url = f"https://{username}:{token}@github.com/{username}/Lab_reserved_TESTING.git"

        # Set the remote URL
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)

        # Stage the file
        subprocess.run(["git", "add", file_path], check=True)

        # Commit the changes
        subprocess.run(["git", "commit", "-m", commit_message], check=True)

        # Push the changes
        subprocess.run(["git", "push"], check=True)

        # st.success(f"Changes to {file_path} have been backed up to GitHub.")
    except subprocess.CalledProcessError as e:
        st.error(f"An error occurred while backing up to GitHub: {e}")

# Load equipment details from JSON
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

# Save equipment details to JSON
def save_equipment_details(details, json_file_path=EQUIPMENT_DETAILS_FILE_PATH):
    try:
        with open(json_file_path, 'w') as file:
            json.dump(details, file, indent=4)
        backup_to_github(json_file_path, commit_message="Update equipment details")
    except Exception as e:
        st.error(f"Error saving equipment details: {e}")

# Check if image exists
def image_exists(image_path):
    return os.path.exists(image_path)

# Safely display image
def safe_display_image(image_path, width=100, offset=0):
    if image_exists(image_path):
        cols = st.columns([offset, 1])
        with cols[1]:
            st.image(image_path, width=width)
    else:
        st.error("Image not available.")

# Convert DataFrame to CSV string
def convert_df_to_csv(df):
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode('utf-8')

# Download non-PCR data
def download_non_pcr():
    df_non_pcr = fetch_data(NON_PCR_FILE_PATH)
    return df_non_pcr

# Download PCR data
def download_pcr():
    df_pcr = fetch_data(PCR_FILE_PATH)
    return df_pcr

# Generate time slots
def generate_time_slots():
    slots = [{
        "label": f"Slot {i + 1}: {datetime.time(hour=h).strftime('%H:%M')}-{datetime.time(hour=h + 3).strftime('%H:%M')}",
        "start": datetime.time(hour=h), "end": datetime.time(hour=h + 3)}
        for i, h in enumerate(range(8, 20, 3))]
    return slots

slots = generate_time_slots()

# Load equipment details once
def load_equipment_details():
    if 'equipment_details' not in st.session_state:
        st.session_state.equipment_details = load_json(EQUIPMENT_DETAILS_FILE_PATH)

load_equipment_details()

# Log actions
def log_action(action, user, details):
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "user": user,
        "details": details
    }

    try:
        if os.path.exists(LOG_FILE_PATH):
            log_df = pd.read_csv(LOG_FILE_PATH)
        else:
            log_df = pd.DataFrame(columns=["timestamp", "action", "user", "details"])

        log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
        log_df.to_csv(LOG_FILE_PATH, index=False)
        save_data(log_df, LOG_FILE_PATH)
    except Exception as e:
        st.error(f"Error logging action: {e}")

def apply_mobile_style():
    # Mobile style
    st.markdown(
        """
        <style>
        .watermark {
            font-size: 15px;
            text-align: left;
            color: gray;
            margin-top: 3px;
        }
        </style>
        """, unsafe_allow_html=True
    )

    st.markdown(
        '<p class="watermark">Designed by Yanawat Pattharapistthorn and TE Group (2024).</p>',
        unsafe_allow_html=True
    )

    css = '''
        <style>
            /* Style adjustments for tabs */
            .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
                font-size: 2rem;
                margin-right: 25px;
            }
            [data-testid="stMarkdownContainer"] {
                font-size: 25px;
                margin-left: 0px;
            }
            /* Welcome message styles */
            .welcome-message {
                font-size: 28px;
                font-family: Arial;
            }
            /* Light and Dark mode adaptations */
            @media (prefers-color-scheme: dark) {
                .welcome-message {
                    color: #DDD; /* Lighter color for dark mode */
                }
                [data-testid="stMarkdownContainer"] {
                    color: #DDD; /* Adjusting text color for dark mode */
                }
            }
            @media (prefers-color-scheme: light) {
                .welcome-message {
                    color: #333; /* Darker color for light mode */
                }
                [data-testid="stMarkdownContainer"] {
                    color: #333; /* Adjusting text color for light mode */
                }
            }
        </style>
    '''
    st.markdown(css, unsafe_allow_html=True)


def apply_web_style():
    # Web style
    st.markdown(
        """
        <style>
        .watermark {
            font-size: 15px;
            text-align: center;
            color: gray;
            margin-top: 3px;
        }
        </style>
        """, unsafe_allow_html=True
    )

    st.markdown(
        '<p class="watermark">Designed by Yanawat Pattharapistthorn and TE Group (2024).</p>',
        unsafe_allow_html=True
    )

    css = '''
    <style>
        /* Style adjustments for tabs */
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 2rem;
            margin-right: 25px;
        }
        [data-testid="stMarkdownContainer"] {
            font-size: 25px;
            margin-left: 0px;
        }
        /* Welcome message styles */
        .welcome-message {
            font-size: 28px;
            font-family: Arial;
        }
        /* Light and Dark mode adaptations */
        @media (prefers-color-scheme: dark) {
            .welcome-message {
                color: #DDD; /* Lighter color for dark mode */
            }
            [data-testid="stMarkdownContainer"] {
                color: #DDD; /* Adjusting text color for dark mode */
            }
        }
        @media (prefers-color-scheme: light) {
            .welcome-message {
                color: #333; /* Darker color for light mode */
            }
            [data-testid="stMarkdownContainer"] {
                color: #333; /* Adjusting text color for light mode */
            }
        }
    </style>
    '''
    st.markdown(css, unsafe_allow_html=True)

# Function to authenticate users
def authenticate(username, password):
    user = st.secrets["credentials"]["usernames"].get(username)
    if user and user["password"] == password:
        return True, user["name"]
    return False, None

# Device type selection in sidebar
mobile = st.toggle('Mobile Version')
announcement_text = read_announcement()
# Apply the appropriate style based on the toggle
if mobile:
    apply_mobile_style()

    credentials = {
        "usernames": {
            user.lower(): {
                "name": st.secrets["credentials"]["usernames"][user]["name"],
                "username": user.lower(),
                "email": st.secrets["credentials"]["usernames"][user]["email"],
                "password": st.secrets["credentials"]["usernames"][user]["password"],
                "role": st.secrets["credentials"]["usernames"][user]["role"]
            }
            for user in st.secrets["credentials"]["usernames"]
        }
    }

    # Check if the user is logged in
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = False
        st.session_state['username'] = None

    if not st.session_state['authentication_status']:
        st.title("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            is_authenticated, name = authenticate(username, password)
            if is_authenticated:
                st.session_state['authentication_status'] = True
                st.session_state['username'] = username
                st.session_state['name'] = name
                st.rerun()
            else:
                st.error("Invalid username or password")

    else:
        role = credentials['usernames'][st.session_state['username'].lower()]['role']
        if st.button("Logout"):
            st.session_state['authentication_status'] = False
            st.session_state['username'] = None
            st.session_state['name'] = None
            st.rerun()  # Rerun the app to refresh the state

        # Always check if there's an announcement to display
        if announcement_text:
            # Using st.markdown to insert HTML for a moving text effect

            st.markdown(

                f"<marquee style='width: 40%; color: red; font-size: 20px;'>{announcement_text}</marquee>",

                unsafe_allow_html=True

            )

        # Usual app interface
        message = f"### Welcome <span class='welcome-message'>{st.session_state['name']}</span>"
        st.markdown(message, unsafe_allow_html=True)

        if role in ["Admins", "Lecturer"]:

            selected_tab = st.selectbox("### Select Actions", ["Reservation Tables", "Reservation Forms", "Reservation Cancellation", "Announcement"])

            if selected_tab == 'Announcement':

                announcement_text = read_announcement()

                st.write("Admin and Lecturer Controls")

                new_announcement_text = st.text_area("Enter announcement:", value=announcement_text)

                if st.button("Update Announcement"):
                    update_announcement(new_announcement_text, ANNOUNCEMENT_FILE_PATH)

                    st.session_state['announcement'] = new_announcement_text

        else:
            selected_tab = st.selectbox("### Select Actions", ["Reservation Tables", "Reservation Forms", "Reservation Cancellation"])


        if selected_tab == "Reservation Tables":
            room_selection = st.selectbox("### Select a Room", list(st.session_state.equipment_details.keys()),
                                          key='tab1 select room')

            # Generate a list of dates for the next week
            dates = [(datetime.date.today() + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(60)]
            view_date = st.selectbox("### View reservations for", dates)
            selected_date = datetime.datetime.strptime(view_date, '%Y-%m-%d').date()

            full_day_start = datetime.datetime.combine(selected_date, datetime.time(0, 0))
            full_day_end = datetime.datetime.combine(selected_date, datetime.time(23, 59))
            pcr_start = datetime.datetime.combine(selected_date, datetime.time(8, 0))
            pcr_end = datetime.datetime.combine(selected_date, datetime.time(20, 0))

            # Read reservation data from CSV files
            df_non_pcr = fetch_data(NON_PCR_FILE_PATH)
            df_non_pcr.dropna(inplace=True)

            df_pcr = fetch_data(PCR_FILE_PATH)
            df_pcr.dropna(inplace=True)

            # Filter DataFrames for the selected day
            df_pcr_filtered = df_pcr[
                (df_pcr['Room'] == room_selection) & (df_pcr['Start_Time'].dt.date == selected_date)]
            df_non_pcr_filtered = df_non_pcr[
                (df_non_pcr['Room'] == room_selection) & (df_non_pcr['Start_Time'].dt.date == selected_date)]

            gantt_df_list_pcr = []
            gantt_df_list_non_pcr = []

            for equipment, details in st.session_state.equipment_details[room_selection].items():
                if details['enabled']:
                    is_pcr_equipment = "PCR" in equipment
                    equipment_reservations = df_pcr_filtered if is_pcr_equipment else df_non_pcr_filtered
                    operational_start = pcr_start if is_pcr_equipment else full_day_start
                    operational_end = pcr_end if is_pcr_equipment else full_day_end

                    filtered_reservations = equipment_reservations[equipment_reservations['Equipments'] == equipment]
                    target_list = gantt_df_list_pcr if is_pcr_equipment else gantt_df_list_non_pcr
                    if filtered_reservations.empty:
                        target_list.append({
                            'Task': equipment,
                            'Start': operational_end,
                            'Finish': operational_end,
                            'User': 'Available'
                        })
                    else:
                        for _, reservation in filtered_reservations.iterrows():
                            start = max(reservation['Start_Time'], operational_start)
                            end = min(reservation['End_Time'], operational_end)
                            target_list.append({
                                'Task': reservation['Equipments'],
                                'Start': start,
                                'Finish': end,
                                'User': reservation['Name']
                            })

            # Generate and display the Gantt chart for PCR equipment
            if gantt_df_list_pcr:
                gantt_df_pcr = pd.DataFrame(gantt_df_list_pcr)
                fig_pcr = px.timeline(gantt_df_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                      title=f"PCR Equipments Reservations for {room_selection}")
                fig_pcr.update_xaxes(range=[pcr_start, pcr_end], tickformat="%H:%M\n%Y-%m-%d", showgrid=True,
                                     gridcolor='LightGrey')
                fig_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_pcr.update_layout(
                    title=dict(
                        text=f"Equipments Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=22),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=14),
                        tickfont=dict(size=12),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipments",
                        title_font=dict(size=14),
                        tickfont=dict(size=12),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=165),  # Adjust if needed
                    height=600,
                    width=530
                )
                for trace in fig_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False
                st.plotly_chart(fig_pcr)

            # Generate and display the Gantt chart for non-PCR equipment
            if gantt_df_list_non_pcr:
                gantt_df_non_pcr = pd.DataFrame(gantt_df_list_non_pcr)
                fig_non_pcr = px.timeline(gantt_df_non_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                          title=f"Non-PCR Equipments Reservations for {room_selection}")
                fig_non_pcr.update_xaxes(range=[full_day_start, full_day_end], tickformat="%H:%M\n%Y-%m-%d",
                                         showgrid=True, gridcolor='LightGrey')
                fig_non_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_non_pcr.update_layout(
                    title=dict(
                        text=f"Equipments Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=22),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=14),
                        tickfont=dict(size=12),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipments",
                        title_font=dict(size=14),
                        tickfont=dict(size=12),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=165),  # Adjust if needed
                    height=600,
                    width=530
                )
                for trace in fig_non_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False

                st.plotly_chart(fig_non_pcr)



        elif selected_tab == "Reservation Forms":

            # Room selection

            selected_room = st.selectbox("### Select a Room", list(st.session_state.equipment_details.keys()))

            # Equipments selection based on the selected room

            # Filter to show only enabled equipments

            enabled_equipments = {eq: info for eq, info in st.session_state.equipment_details[selected_room].items() if

                                  info.get('enabled', False)}

            selected_equipment = st.selectbox("### Select Equipments", list(enabled_equipments.keys()))

            # Fetch equipment information

            equipment_info = enabled_equipments[selected_equipment]

            # Display selected equipment details and image

            safe_display_image(equipment_info['image'], width=300, offset=0.5)  # Adjust width as necessary

            st.write(f"#### Details : {equipment_info['details']}")

            if "PCR" in selected_equipment:

                st.subheader("Book Your PCR Slot")

                # Date and slot selection within the form to prevent re-run on change

                today = datetime.date.today()

                tomorrow = today + datetime.timedelta(days=1)

                reservation_date = st.date_input("## Reservation Date", min_value=today, max_value=tomorrow)

                current_datetime = datetime.datetime.now()

                slots = generate_time_slots()  # Function to generate time slots

                if reservation_date == today:
                    slots = [slot for slot in slots if

                             datetime.datetime.combine(today, slot['end']) > current_datetime]

                if slots:

                    available_slots = [slot['label'] for slot in slots]

                    selected_slot_label = st.selectbox("## Select a Time Slot", available_slots)

                    selected_slot = next((slot for slot in slots if slot['label'] == selected_slot_label), None)

                else:

                    st.error("No available slots for the selected day.")

                if st.button('### Submit PCR Reservation'):

                    df_pcr = fetch_data(PCR_FILE_PATH)

                    df_pcr.dropna(inplace=True)

                    start_datetime = datetime.datetime.combine(reservation_date, selected_slot['start'])

                    end_datetime = datetime.datetime.combine(reservation_date, selected_slot['end'])

                    # Convert start and end times to datetime format

                    df_pcr['Start_Time'] = pd.to_datetime(df_pcr['Start_Time'])

                    df_pcr['End_Time'] = pd.to_datetime(df_pcr['End_Time'])

                    # Filter user's reservations on the same day for the same room and equipment

                    user_reservations = df_pcr[

                        (df_pcr['Name'] == st.session_state["name"]) &

                        (df_pcr['Room'] == selected_room) &

                        (df_pcr['Equipments'] == selected_equipment) &

                        (df_pcr['Start_Time'].dt.date == reservation_date)

                        ]

                    continuous_slot_booked = False

                    for _, res in user_reservations.iterrows():

                        if res['End_Time'] == start_datetime or res['Start_Time'] == end_datetime:
                            continuous_slot_booked = True

                            break

                    # Check for overlapping reservations

                    overlapping_reservations = df_pcr[

                        (df_pcr['Room'] == selected_room) &

                        (df_pcr['Equipments'] == selected_equipment) &

                        ((df_pcr['Start_Time'] < end_datetime) & (df_pcr['End_Time'] > start_datetime))

                        ]

                    if not overlapping_reservations.empty:

                        st.error("This slot is already booked. Please choose another slot.")

                    elif continuous_slot_booked:

                        st.error("Cannot book continuous slots. Please select a non-continuous slot.")

                    else:

                        # Create and add new reservation

                        new_reservation = pd.DataFrame([{

                            'Name': st.session_state["name"],

                            'Room': selected_room,

                            'Equipments': selected_equipment,

                            'Start_Time': start_datetime,

                            'End_Time': end_datetime

                        }])

                        # Concatenate the DataFrames

                        df_pcr_buffer = pd.concat([df_pcr, new_reservation], ignore_index=True)

                        df_pcr_buffer.reset_index(drop=True, inplace=True)

                        df_pcr_buffer['Start_Time'] = df_pcr_buffer['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        df_pcr_buffer['End_Time'] = df_pcr_buffer['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        log_action("Add Reservation", st.session_state["name"], new_reservation)

                        # Save the updated DataFrame back to the CSV file

                        save_data(df_pcr_buffer, PCR_FILE_PATH)

                        st.success(

                            f"Reservation successful for {selected_equipment} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")


            else:

                st.subheader(f"Reserve {selected_equipment}")

                # Non-PCR Equipment reservation logic

                max_days_advance = 60 if role in ["Admins", "Lecturer"] else 30

                if "Autoclave" in selected_equipment:
                    max_days_advance = min(max_days_advance, 1)

                max_date = datetime.date.today() + datetime.timedelta(days=max_days_advance)

                start_date = st.date_input("## Start Date", min_value=datetime.date.today(), max_value=max_date)

                current_time = datetime.datetime.now()

                min_time = current_time.time() if start_date == datetime.date.today() else datetime.time(0, 0)

                start_time = st.time_input("## Start Time", value=None)

                end_time = st.time_input("## End Time", value=None)

                if start_time and end_time:

                    start_datetime = datetime.datetime.combine(start_date, start_time)

                    end_datetime = datetime.datetime.combine(start_date, end_time)

                    if st.button("### Submit Reservation"):

                        df_non_pcr = fetch_data(NON_PCR_FILE_PATH)

                        df_non_pcr.dropna(inplace=True)

                        if start_datetime < current_time:

                            st.error("Cannot book a reservation in the past. Please select a future time.")

                        elif start_datetime >= end_datetime:

                            st.error("The start time must be before the end time. Please adjust your selection.")

                        else:

                            # Check for overlapping reservations

                            overlapping_reservations = df_non_pcr[

                                (df_non_pcr['Room'] == selected_room) &

                                (df_non_pcr['Equipments'] == selected_equipment) &

                                ((df_non_pcr['Start_Time'] < end_datetime) & (df_non_pcr['End_Time'] > start_datetime))

                                ]

                            if not overlapping_reservations.empty:

                                st.error("This time slot is already reserved. Please choose another time.")

                            else:

                                new_reservation = {

                                    'Name': st.session_state["name"],

                                    'Room': selected_room,

                                    'Equipments': selected_equipment,

                                    'Start_Time': start_datetime,

                                    'End_Time': end_datetime

                                }

                                new_reservation_df = pd.DataFrame([new_reservation])

                                df_non_pcr_buffer = pd.concat([df_non_pcr, new_reservation_df], ignore_index=True)

                                df_non_pcr_buffer.reset_index(drop=True, inplace=True)

                                df_non_pcr_buffer['Start_Time'] = df_non_pcr_buffer['Start_Time'].dt.strftime(
                                    '%Y/%m/%d %H:%M:%S')

                                df_non_pcr_buffer['End_Time'] = df_non_pcr_buffer['End_Time'].dt.strftime(
                                    '%Y/%m/%d %H:%M:%S')

                                # Save the updated DataFrame back to the CSV file

                                save_data(df_non_pcr_buffer, NON_PCR_FILE_PATH)

                                # Handle autoclave usage counting

                                if selected_equipment in ['Autoclave 1 (Drain the water every 5 times after using)',

                                                          'Autoclave 2 (Drain the water every 5 times after using)']:

                                    autoclaves_count = load_data(AUTOCLAVES_PATH)

                                    current_count = len(
                                        autoclaves_count[autoclaves_count['Counts'] == selected_equipment])

                                    new_count = current_count + 1

                                    if new_count >= 5:

                                        st.info(
                                            "You are the fifth user of this autoclave. Please remember to drain the water after using it.")

                                        autoclaves_count = autoclaves_count.drop(
                                            autoclaves_count[autoclaves_count['Counts'] == selected_equipment].index)

                                        save_data(autoclaves_count, AUTOCLAVES_PATH)

                                    else:

                                        st.info(f"You are the {new_count} user of this autoclave.")

                                        counts = {'Counts': selected_equipment}

                                        counts_df = pd.DataFrame([counts])

                                        autoclaves_count_buffer = pd.concat([autoclaves_count, counts_df],
                                                                            ignore_index=True)

                                        save_data(autoclaves_count_buffer, AUTOCLAVES_PATH)

                                log_action("Add Reservation", st.session_state["name"], new_reservation)

                                st.success(

                                    f"Reservation successful for {selected_equipment} in {selected_room} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")



        elif selected_tab == "Reservation Cancellation":

            df_non_pcr = fetch_data(NON_PCR_FILE_PATH)

            df_non_pcr.dropna(inplace=True)

            df_pcr = fetch_data(PCR_FILE_PATH)

            df_pcr.dropna(inplace=True)

            # Combining both dataframes to get user-specific reservations

            user_reservations_pcr = df_pcr[df_pcr['Name'] == st.session_state["name"]]

            user_reservations_non_pcr = df_non_pcr[df_non_pcr['Name'] == st.session_state["name"]]

            user_reservations = pd.concat([user_reservations_pcr, user_reservations_non_pcr])

            # Current datetime

            current_datetime = datetime.datetime.now()

            # Current date and tomorrow's date for filtering

            today = datetime.date.today()

            max_date_60 = today + datetime.timedelta(days=60)

            user_reservations = user_reservations[

                ((user_reservations['Start_Time'].dt.date == today) |

                 ((user_reservations['Start_Time'].dt.date > today) & (
                             user_reservations['Start_Time'] > current_datetime)))

                & (user_reservations['Start_Time'].dt.date <= max_date_60)

                ]

            if not user_reservations.empty:

                # Display the reservations in a selectbox

                selected_reservation_index = st.selectbox(

                    "## Your Reservations:",

                    options=range(len(user_reservations)),

                    format_func=lambda x: f"{user_reservations.iloc[x]['Equipments']} on " +

                                          (user_reservations.iloc[x]['Start_Time'].strftime(
                                              '%Y/%m/%d %H:%M:%S') + ' To ' + user_reservations.iloc[x][
                                               'End_Time'].strftime('%Y/%m/%d %H:%M:%S') if pd.notnull(

                                              user_reservations.iloc[x]['Start_Time']) else "Date not available")

                )

                # Cancel reservation button

                if st.button("### Cancel Reservation"):

                    # Remove the selected reservation

                    reservation_to_cancel = user_reservations.iloc[selected_reservation_index]

                    if "PCR" in reservation_to_cancel['Equipments']:

                        df_pcr.drop(index=reservation_to_cancel.name, inplace=True)

                        df_pcr['Start_Time'] = df_pcr['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        df_pcr['End_Time'] = df_pcr['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        log_action("Delete Reservation", st.session_state["name"], f"Details: {user_reservations.iloc[selected_reservation_index]}")

                        save_data(df_pcr, PCR_FILE_PATH)  # Save updated dataframe back to CSV

                    else:

                        df_non_pcr.drop(index=reservation_to_cancel.name, inplace=True)

                        df_non_pcr['Start_Time'] = df_non_pcr['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        df_non_pcr['End_Time'] = df_non_pcr['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        log_action("Delete Reservation", st.session_state["name"], f"Details: {user_reservations.iloc[selected_reservation_index]}")

                        save_data(df_non_pcr, NON_PCR_FILE_PATH)  # Save updated dataframe back to CSV

                    st.success("Reservation canceled successfully.")

            else:

                st.write("## You have no reservations.")

else:
    apply_web_style()

    credentials = {
        "usernames": {
            user.lower(): {
                "name": st.secrets["credentials"]["usernames"][user]["name"],
                "username": user.lower(),
                "email": st.secrets["credentials"]["usernames"][user]["email"],
                "password": st.secrets["credentials"]["usernames"][user]["password"],
                "role": st.secrets["credentials"]["usernames"][user]["role"]
            }
            for user in st.secrets["credentials"]["usernames"]
        }
    }

    # Check if the user is logged in
    if 'authentication_status' not in st.session_state:
        st.session_state['authentication_status'] = False
        st.session_state['username'] = None

    if not st.session_state['authentication_status']:
        st.title("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            is_authenticated, name = authenticate(username, password)
            if is_authenticated:
                st.session_state['authentication_status'] = True
                st.session_state['username'] = username
                st.session_state['name'] = name
                st.rerun()
            else:
                st.error("Invalid username or password")

    else:
        role = credentials['usernames'][st.session_state['username'].lower()]['role']

        # Check if the user is authorized (either an admin or a lecturer) and allow them to post an announcement
        if role in ["Admins", "Lecturer"]:
            with st.sidebar:
                st.write("Admin and Lecturer Controls")
                new_announcement_text = st.text_area("### Enter announcement:", value=announcement_text)
                if st.button("Update Announcement"):
                    update_announcement(new_announcement_text,ANNOUNCEMENT_FILE_PATH)
                    st.session_state['announcement'] = new_announcement_text

        # Always check if there's an announcement to display
        if announcement_text:
            # Using st.markdown to insert HTML for a moving text effect
            st.markdown(
                f"<marquee style='width: 100%; color: red; font-size: 24px;'>{announcement_text}</marquee>",
                unsafe_allow_html=True
            )

        message = f"### Welcome <span class='welcome-message'>{st.session_state['name']}</span>"
        st.markdown(message, unsafe_allow_html=True)
        if st.sidebar.button("Logout"):
            st.session_state['authentication_status'] = False
            st.session_state['username'] = None
            st.session_state['name'] = None
            st.rerun()  # Rerun the app to refresh the state

        if role == "Admins":
            tab1, tab2, tab3, tab5 = st.tabs(["Reservation Tables", "Reservation Forms", "Reservation Cancellation", "Admins Interface"])
        else:
            tab1, tab2, tab3, tab4 = st.tabs(["Reservation Tables", "Reservation Forms", "Reservation Cancellation", "Contact Us"])

        st.sidebar.download_button(
            label="Download General Reservations as CSV",
            data=convert_df_to_csv(download_non_pcr()),
            file_name='general_reservations.csv',
            mime='text/csv'
        )

        st.sidebar.download_button(
            label="Download PCR Reservations as CSV",
            data=convert_df_to_csv(download_pcr()),
            file_name='pcr_reservations.csv',
            mime='text/csv'
        )

        with tab1:
            room_selection = st.selectbox("### Select a Room", list(st.session_state.equipment_details.keys()), key='tab1 select room')

            # Generate a list of dates for the next week
            dates = [(datetime.date.today() + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(60)]
            view_date = st.selectbox("### View reservations for", dates)
            selected_date = datetime.datetime.strptime(view_date, '%Y-%m-%d').date()

            full_day_start = datetime.datetime.combine(selected_date, datetime.time(0, 0))
            full_day_end = datetime.datetime.combine(selected_date, datetime.time(23, 59))
            pcr_start = datetime.datetime.combine(selected_date, datetime.time(8, 0))
            pcr_end = datetime.datetime.combine(selected_date, datetime.time(20, 0))

            # Read reservation data from CSV files
            df_non_pcr = fetch_data(NON_PCR_FILE_PATH)
            df_non_pcr.dropna(inplace=True)

            df_pcr = fetch_data(PCR_FILE_PATH)
            df_pcr.dropna(inplace=True)

            # Filter DataFrames for the selected day
            df_pcr_filtered = df_pcr[(df_pcr['Room'] == room_selection) & (df_pcr['Start_Time'].dt.date == selected_date)]
            df_non_pcr_filtered = df_non_pcr[
                (df_non_pcr['Room'] == room_selection) & (df_non_pcr['Start_Time'].dt.date == selected_date)]

            gantt_df_list_pcr = []
            gantt_df_list_non_pcr = []

            for equipment, details in st.session_state.equipment_details[room_selection].items():
                if details['enabled']:
                    is_pcr_equipment = "PCR" in equipment
                    equipment_reservations = df_pcr_filtered if is_pcr_equipment else df_non_pcr_filtered
                    operational_start = pcr_start if is_pcr_equipment else full_day_start
                    operational_end = pcr_end if is_pcr_equipment else full_day_end

                    filtered_reservations = equipment_reservations[equipment_reservations['Equipments'] == equipment]
                    target_list = gantt_df_list_pcr if is_pcr_equipment else gantt_df_list_non_pcr
                    if filtered_reservations.empty:
                        target_list.append({
                            'Task': equipment,
                            'Start': operational_end,
                            'Finish': operational_end,
                            'User': 'Available'
                        })
                    else:
                        for _, reservation in filtered_reservations.iterrows():
                            start = max(reservation['Start_Time'], operational_start)
                            end = min(reservation['End_Time'], operational_end)
                            target_list.append({
                                'Task': reservation['Equipments'],
                                'Start': start,
                                'Finish': end,
                                'User': reservation['Name']
                            })

            # Generate and display the Gantt chart for PCR equipment
            if gantt_df_list_pcr:
                gantt_df_pcr = pd.DataFrame(gantt_df_list_pcr)
                fig_pcr = px.timeline(gantt_df_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                      title=f"PCR Equipments Reservations for {room_selection}")
                fig_pcr.update_xaxes(range=[pcr_start, pcr_end], tickformat="%H:%M\n%Y-%m-%d", showgrid=True,
                                     gridcolor='LightGrey')
                fig_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_pcr.update_layout(
                    title=dict(
                        text=f"Equipments Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=26),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipments",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=200),  # Adjust if needed
                    height=600,
                    width=1000
                )
                for trace in fig_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False
                st.plotly_chart(fig_pcr)

            # Generate and display the Gantt chart for non-PCR equipment
            if gantt_df_list_non_pcr:
                gantt_df_non_pcr = pd.DataFrame(gantt_df_list_non_pcr)
                fig_non_pcr = px.timeline(gantt_df_non_pcr, x_start="Start", x_end="Finish", y="Task", color="User",
                                          title=f"Non-PCR Equipments Reservations for {room_selection}")
                fig_non_pcr.update_xaxes(range=[full_day_start, full_day_end], tickformat="%H:%M\n%Y-%m-%d",
                                         showgrid=True,
                                         gridcolor='LightGrey')
                fig_non_pcr.update_yaxes(showgrid=True, gridcolor='LightGrey')
                fig_non_pcr.update_layout(
                    title=dict(
                        text=f"Equipments Reservations for {room_selection}",
                        # Also corrected here if updating layout separately
                        font=dict(size=26),
                        x=0,
                        y=0.95,
                    ),
                    xaxis=dict(
                        title="Time",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey",
                        side="top",
                        dtick=7200000,  # 2 hour in milliseconds
                        tickformat="%H:%M\n%Y-%m-%d"  # Adjust if needed to match your desired format
                    ),
                    yaxis=dict(
                        title="Equipments",
                        title_font=dict(size=20),
                        tickfont=dict(size=18),
                        showgrid=True,
                        gridcolor="LightGrey"
                    ),
                    margin=dict(t=200),  # Adjust if needed
                    height=600,
                    width=1000
                )
                for trace in fig_non_pcr.data:
                    if trace.name == "Available":
                        trace.showlegend = False

                st.plotly_chart(fig_non_pcr)

        with tab2:
            # Room selection
            selected_room = st.selectbox("### Select a Room", list(st.session_state.equipment_details.keys()))

            # Equipments selection based on the selected room
            # Filter to show only enabled equipments
            enabled_equipments = {eq: info for eq, info in st.session_state.equipment_details[selected_room].items() if
                                  info.get('enabled', False)}

            selected_equipment = st.selectbox("### Select Equipments", list(enabled_equipments.keys()))

            # Fetch equipment information
            equipment_info = enabled_equipments[selected_equipment]

            # Display selected equipment details and image
            safe_display_image(equipment_info['image'], width=450, offset=0.5)  # Adjust width as necessary
            st.write(f"#### Details : {equipment_info['details']}")

            if "PCR" in selected_equipment:
                st.subheader("Book Your PCR Slot")

                # Date and slot selection within the form to prevent re-run on change
                today = datetime.date.today()
                tomorrow = today + datetime.timedelta(days=1)
                reservation_date = st.date_input("## Reservation Date", min_value=today, max_value=tomorrow)

                current_datetime = datetime.datetime.now()
                slots = generate_time_slots()  # Function to generate time slots
                if reservation_date == today:
                    slots = [slot for slot in slots if
                             datetime.datetime.combine(today, slot['end']) > current_datetime]

                if slots:
                    available_slots = [slot['label'] for slot in slots]
                    selected_slot_label = st.selectbox("## Select a Time Slot", available_slots)
                    selected_slot = next((slot for slot in slots if slot['label'] == selected_slot_label), None)
                else:
                    st.error("No available slots for the selected day.")

                if st.button('### Submit PCR Reservation'):
                    df_pcr = fetch_data(PCR_FILE_PATH)
                    df_pcr.dropna(inplace=True)

                    start_datetime = datetime.datetime.combine(reservation_date, selected_slot['start'])
                    end_datetime = datetime.datetime.combine(reservation_date, selected_slot['end'])

                    # Convert start and end times to datetime format
                    df_pcr['Start_Time'] = pd.to_datetime(df_pcr['Start_Time'])
                    df_pcr['End_Time'] = pd.to_datetime(df_pcr['End_Time'])

                    # Filter user's reservations on the same day for the same room and equipment
                    user_reservations = df_pcr[
                        (df_pcr['Name'] == st.session_state["name"]) &
                        (df_pcr['Room'] == selected_room) &
                        (df_pcr['Equipments'] == selected_equipment) &
                        (df_pcr['Start_Time'].dt.date == reservation_date)
                        ]

                    continuous_slot_booked = False
                    for _, res in user_reservations.iterrows():
                        if res['End_Time'] == start_datetime or res['Start_Time'] == end_datetime:
                            continuous_slot_booked = True
                            break

                    # Check for overlapping reservations
                    overlapping_reservations = df_pcr[
                        (df_pcr['Room'] == selected_room) &
                        (df_pcr['Equipments'] == selected_equipment) &
                        ((df_pcr['Start_Time'] < end_datetime) & (df_pcr['End_Time'] > start_datetime))
                        ]

                    if not overlapping_reservations.empty:
                        st.error("This slot is already booked. Please choose another slot.")
                    elif continuous_slot_booked:
                        st.error("Cannot book continuous slots. Please select a non-continuous slot.")
                    else:
                        # Create and add new reservation
                        new_reservation = pd.DataFrame([{
                            'Name': st.session_state["name"],
                            'Room': selected_room,
                            'Equipments': selected_equipment,
                            'Start_Time': start_datetime,
                            'End_Time': end_datetime
                        }])

                        # Concatenate the DataFrames
                        df_pcr_buffer = pd.concat([df_pcr, new_reservation], ignore_index=True)
                        df_pcr_buffer.reset_index(drop=True, inplace=True)

                        df_pcr_buffer['Start_Time'] = df_pcr_buffer['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')
                        df_pcr_buffer['End_Time'] = df_pcr_buffer['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')

                        # Save the updated DataFrame back to the CSV file
                        save_data(df_pcr_buffer, PCR_FILE_PATH)

                        log_action("Add Reservation", st.session_state["name"], new_reservation)

                        st.success(
                            f"Reservation successful for {selected_equipment} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")



            else:

                st.subheader(f"Reserve {selected_equipment}")

                # Non-PCR Equipment reservation logic

                max_days_advance = 60 if role in ["Admins", "Lecturer"] else 30

                if "Autoclave" in selected_equipment:
                    max_days_advance = min(max_days_advance, 1)

                max_date = datetime.date.today() + datetime.timedelta(days=max_days_advance)

                start_date = st.date_input("## Start Date", min_value=datetime.date.today(), max_value=max_date)

                current_time = datetime.datetime.now()

                min_time = current_time.time() if start_date == datetime.date.today() else datetime.time(0, 0)

                start_time = st.time_input("## Start Time", value=None)

                end_time = st.time_input("## End Time", value=None)

                if start_time and end_time:

                    start_datetime = datetime.datetime.combine(start_date, start_time)

                    end_datetime = datetime.datetime.combine(start_date, end_time)

                    if st.button("### Submit Reservation"):

                        df_non_pcr = fetch_data(NON_PCR_FILE_PATH)

                        df_non_pcr.dropna(inplace=True)

                        if start_datetime < current_time:

                            st.error("Cannot book a reservation in the past. Please select a future time.")

                        elif start_datetime >= end_datetime:

                            st.error("The start time must be before the end time. Please adjust your selection.")

                        else:

                            # Check for overlapping reservations

                            overlapping_reservations = df_non_pcr[

                                (df_non_pcr['Room'] == selected_room) &

                                (df_non_pcr['Equipments'] == selected_equipment) &

                                ((df_non_pcr['Start_Time'] < end_datetime) & (df_non_pcr['End_Time'] > start_datetime))

                                ]

                            if not overlapping_reservations.empty:

                                st.error("This time slot is already reserved. Please choose another time.")

                            else:

                                new_reservation = {

                                    'Name': st.session_state["name"],

                                    'Room': selected_room,

                                    'Equipments': selected_equipment,

                                    'Start_Time': start_datetime,

                                    'End_Time': end_datetime

                                }

                                new_reservation_df = pd.DataFrame([new_reservation])

                                df_non_pcr_buffer = pd.concat([df_non_pcr, new_reservation_df], ignore_index=True)

                                df_non_pcr_buffer.reset_index(drop=True, inplace=True)

                                df_non_pcr_buffer['Start_Time'] = df_non_pcr_buffer['Start_Time'].dt.strftime(
                                    '%Y/%m/%d %H:%M:%S')

                                df_non_pcr_buffer['End_Time'] = df_non_pcr_buffer['End_Time'].dt.strftime(
                                    '%Y/%m/%d %H:%M:%S')

                                # Save the updated DataFrame back to the CSV file

                                save_data(df_non_pcr_buffer, NON_PCR_FILE_PATH)

                                # Handle autoclave usage counting

                                if selected_equipment in ['Autoclave 1 (Drain the water every 5 times after using)',

                                                          'Autoclave 2 (Drain the water every 5 times after using)']:

                                    autoclaves_count = load_data(AUTOCLAVES_PATH)

                                    current_count = len(
                                        autoclaves_count[autoclaves_count['Counts'] == selected_equipment])

                                    new_count = current_count + 1

                                    if new_count >= 5:

                                        st.info(
                                            "You are the fifth user of this autoclave. Please remember to drain the water after using it.")

                                        autoclaves_count = autoclaves_count.drop(
                                            autoclaves_count[autoclaves_count['Counts'] == selected_equipment].index)

                                        save_data(autoclaves_count, AUTOCLAVES_PATH)

                                    else:

                                        st.info(f"You are the {new_count} user of this autoclave.")

                                        counts = {'Counts': selected_equipment}

                                        counts_df = pd.DataFrame([counts])

                                        autoclaves_count_buffer = pd.concat([autoclaves_count, counts_df],
                                                                            ignore_index=True)

                                        save_data(autoclaves_count_buffer, AUTOCLAVES_PATH)

                                log_action("Add Reservation", st.session_state["name"],new_reservation)
                                st.success(

                                    f"Reservation successful for {selected_equipment} in {selected_room} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")

        with tab3:
            df_non_pcr = fetch_data(NON_PCR_FILE_PATH)
            df_non_pcr.dropna(inplace=True)

            df_pcr = fetch_data(PCR_FILE_PATH)
            df_pcr.dropna(inplace=True)

            # Combining both dataframes to get user-specific reservations
            user_reservations_pcr = df_pcr[df_pcr['Name'] == st.session_state["name"]]
            user_reservations_non_pcr = df_non_pcr[df_non_pcr['Name'] == st.session_state["name"]]
            user_reservations = pd.concat([user_reservations_pcr, user_reservations_non_pcr])

            # Current datetime
            current_datetime = datetime.datetime.now()

            # Current date and tomorrow's date for filtering
            today = datetime.date.today()
            max_date_60 = today + datetime.timedelta(days=60)

            user_reservations = user_reservations[
                ((user_reservations['Start_Time'].dt.date == today) |
                 ((user_reservations['Start_Time'].dt.date > today) & (
                             user_reservations['Start_Time'] > current_datetime)))
                & (user_reservations['Start_Time'].dt.date <= max_date_60)
                ]

            if not user_reservations.empty:
                # Display the reservations in a selectbox
                selected_reservation_index = st.selectbox(
                    "## Your Reservations:",
                    options=range(len(user_reservations)),
                    format_func=lambda x: f"{user_reservations.iloc[x]['Equipments']} on " +
                                          (user_reservations.iloc[x]['Start_Time'].strftime(
                                              '%Y/%m/%d %H:%M:%S') + ' To ' + user_reservations.iloc[x][
                                               'End_Time'].strftime('%Y/%m/%d %H:%M:%S') if pd.notnull(
                                              user_reservations.iloc[x]['Start_Time']) else "Date not available")
                )

                # Cancel reservation button
                if st.button("### Cancel Reservation"):
                    # Remove the selected reservation
                    reservation_to_cancel = user_reservations.iloc[selected_reservation_index]
                    if "PCR" in reservation_to_cancel['Equipments']:
                        df_pcr.drop(index=reservation_to_cancel.name, inplace=True)
                        df_pcr['Start_Time'] = df_pcr['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')
                        df_pcr['End_Time'] = df_pcr['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')
                        log_action("Delete Reservation", st.session_state["name"], f"Details: {user_reservations.iloc[selected_reservation_index]}")
                        save_data(df_pcr, PCR_FILE_PATH)  # Save updated dataframe back to CSV
                    else:
                        df_non_pcr.drop(index=reservation_to_cancel.name, inplace=True)
                        df_non_pcr['Start_Time'] = df_non_pcr['Start_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')
                        df_non_pcr['End_Time'] = df_non_pcr['End_Time'].dt.strftime('%Y/%m/%d %H:%M:%S')
                        log_action("Delete Reservation", st.session_state["name"], f"Details: {user_reservations.iloc[selected_reservation_index]}")
                        save_data(df_non_pcr, NON_PCR_FILE_PATH)  # Save updated dataframe back to CSV

                    st.success("Reservation canceled successfully.")
            else:
                st.write("## You have no reservations.")

        if role != 'Admins':
            with tab4:
                st.subheader("Error reports or Inconvenient issues")

                contact_form = """
                <form action="https://formsubmit.co/geneticsku.services@gmail.com" method="POST">
                     <input type="hidden" name="_captcha" value="false">
                     <input type="text" name="name" placeholder="Your name" required>
                     <input type="email" name="email" placeholder="Your email" required>
                     <textarea name="message" placeholder="Your message here"></textarea>
                     <button type="submit">Send</button>
                </form>
                """

                st.markdown(contact_form, unsafe_allow_html=True)

        if role == "Admins":
            def admin_interface():
                st.write("### PCR Data")
                df_pcr = load_data(PCR_FILE_PATH)
                st.dataframe(df_pcr)

                st.write("### Non-PCR Data")
                df_non_pcr = load_data(NON_PCR_FILE_PATH)
                st.dataframe(df_non_pcr)

                st.write("### Autoclaves Counts")
                autoclaves_count = load_data(AUTOCLAVES_PATH)
                st.dataframe(autoclaves_count)

                st.write("### Logs")
                logs = load_data(LOG_FILE_PATH)
                st.dataframe(logs)

                st.write("### Manage Data")

                # Add new reservation
                st.write("#### Add New Reservation")
                name = st.text_input("Name")

                selected_room = st.selectbox("Room", list(st.session_state.equipment_details.keys()))
                enabled_equipments = {eq: info for eq, info in st.session_state.equipment_details[selected_room].items()
                                      if info.get('enabled', False)}
                selected_equipment = st.selectbox("Equipment", list(enabled_equipments.keys()))

                if "PCR" in selected_equipment:
                    st.subheader("Book Your PCR Slot")
                    reservation_date = st.date_input("## Reservation Date")
                    start_time = st.time_input("## Start Time")
                    end_time = st.time_input("## End Time")

                    start_datetime = datetime.datetime.combine(reservation_date, start_time)
                    end_datetime = datetime.datetime.combine(reservation_date, end_time)

                else:
                    st.subheader(f"Reserve {selected_equipment}")
                    start_date = st.date_input("## Start Date")
                    start_time = st.time_input("## Start Time")
                    end_time = st.time_input("## End Time")

                    start_datetime = datetime.datetime.combine(start_date, start_time)
                    end_datetime = datetime.datetime.combine(start_date, end_time)

                if st.button("Add Reservation"):
                    try:
                        new_reservation = pd.DataFrame([{
                            "Name": name,
                            "Room": selected_room,
                            "Equipments": selected_equipment,
                            "Start_Time": start_datetime,
                            "End_Time": end_datetime
                        }])
                        if "PCR" in selected_equipment:
                            df_pcr = pd.concat([df_pcr, new_reservation], ignore_index=True)
                            save_data(df_pcr, PCR_FILE_PATH)
                        else:
                            df_non_pcr = pd.concat([df_non_pcr, new_reservation], ignore_index=True)
                            save_data(df_non_pcr, NON_PCR_FILE_PATH)
                        st.success("Reservation added successfully.")
                        df_pcr = load_data(PCR_FILE_PATH)
                        df_non_pcr = load_data(NON_PCR_FILE_PATH)

                    except Exception as e:
                        st.error(f"Error adding reservation: {e}")

                # Delete a reservation
                st.write("#### Delete Reservation")
                delete_id = st.text_input("Reservation ID to Delete")
                delete_from_pcr = st.checkbox("Delete from PCR Data", value=True)

                if st.button("Delete Reservation"):
                    try:
                        if delete_from_pcr:
                            df_pcr = df_pcr.drop(index=int(delete_id))
                            save_data(df_pcr, PCR_FILE_PATH)
                        else:
                            df_non_pcr = df_non_pcr.drop(index=int(delete_id))
                            save_data(df_non_pcr, NON_PCR_FILE_PATH)
                        st.success("Reservation deleted successfully.")
                        df_pcr = load_data(PCR_FILE_PATH)
                        df_non_pcr = load_data(NON_PCR_FILE_PATH)

                    except Exception as e:
                        st.error(f"Error deleting reservation: {e}")

                # Update a reservation
                st.write("#### Update Reservation")
                update_id = st.text_input("Reservation ID to Update")
                update_field = st.selectbox("Field to Update", ["Name", "Room", "Equipments", "Start_Time", "End_Time"])
                new_value = st.text_input("New Value")
                update_in_pcr = st.checkbox("Update in PCR Data", value=True)

                if st.button("Update Reservation"):
                    try:
                        if update_in_pcr:
                            if update_field in ["Start_Time", "End_Time"]:
                                df_pcr.at[int(update_id), update_field] = pd.to_datetime(new_value)
                            else:
                                df_pcr.at[int(update_id), update_field] = new_value
                            save_data(df_pcr, PCR_FILE_PATH)
                        else:
                            if update_field in ["Start_Time", "End_Time"]:
                                df_non_pcr.at[int(update_id), update_field] = pd.to_datetime(new_value)
                            else:
                                df_non_pcr.at[int(update_id), update_field] = new_value
                            save_data(df_non_pcr, NON_PCR_FILE_PATH)
                        st.success("Reservation updated successfully.")
                    except Exception as e:
                        st.error(f"Error updating reservation: {e}")

                # Update autoclaves count
                st.write("#### Update Autoclaves Count")
                autoclave_options = ["Autoclave 1 (Drain the water every 5 times after using)",
                                     "Autoclave 2 (Drain the water every 5 times after using)"]
                selected_autoclave = st.selectbox("Select Autoclave", autoclave_options)
                new_count = st.number_input("New Count", min_value=0, step=1)

                if st.button("Update Autoclave Count"):
                    try:
                        autoclaves_count = load_data(AUTOCLAVES_PATH)
                        autoclaves_count = autoclaves_count[autoclaves_count['Counts'] != selected_autoclave]
                        new_entries = pd.DataFrame([{'Counts': selected_autoclave}] * new_count)
                        autoclaves_count = pd.concat([autoclaves_count, new_entries], ignore_index=True)
                        save_data(autoclaves_count, AUTOCLAVES_PATH)
                        st.success(f"{selected_autoclave} count updated successfully.")
                    except Exception as e:
                        st.error(f"Error updating autoclave count: {e}")

                # Equipment Availability
                st.write("### Equipment Availability")
                selected_room_admin = st.selectbox("Select a room to manage equipment:",
                                                           list(st.session_state.equipment_details.keys()))
                equipment_list = list(st.session_state.equipment_details[selected_room_admin].keys())
                selected_equipment_admin = st.selectbox("Select equipment to toggle availability:",
                                                                equipment_list)

                if st.button("Toggle Availability"):
                    # Toggle equipment availability status
                    current_status = st.session_state.equipment_details[selected_room_admin][selected_equipment_admin][
                        'enabled']
                    st.session_state.equipment_details[selected_room_admin][selected_equipment_admin][
                        'enabled'] = not current_status
                    # Show success message and save updated status
                    st.success(f"{'Disabled' if current_status else 'Enabled'} {selected_equipment_admin}")
                    save_equipment_details(st.session_state.equipment_details)

                # File upload to update data
                st.write("#### Upload CSV to Update Data")
                uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
                update_pcr = st.checkbox("Update PCR Data", value=True)

                if uploaded_file is not None:
                    if st.button("Update Data"):
                        try:
                            uploaded_df = pd.read_csv(uploaded_file)
                            if update_pcr:
                                save_data(uploaded_df, PCR_FILE_PATH)
                                st.success("PCR data updated successfully.")
                            else:
                                save_data(uploaded_df, NON_PCR_FILE_PATH)
                                st.success("Non-PCR data updated successfully.")
                        except Exception as e:
                            st.error(f"Error updating data: {e}")


            with tab5:
                st.write("## Admins Interface")
                st.write("You can view and manipulate the data frames here.")
                admin_interface()

            # Use Local CSS File
            def local_css(file_name):
                with open(file_name) as f:
                    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


            local_css("style.css")
