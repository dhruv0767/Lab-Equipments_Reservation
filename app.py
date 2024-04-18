import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import datetime
import plotly.express as px
import json
from io import StringIO
import os, time
from streamlit_gsheets import GSheetsConnection

st.set_page_config(layout="wide")

# Initialize connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Set the timezone
os.environ['TZ'] = 'Asia/Bangkok'
time.tzset()

# Manually extract credentials and prepare them in the expected format
credentials = {
    "usernames": {
        user: {
            "name": st.secrets["credentials"]["usernames"][user]["name"],
            "username": user,
            "email": st.secrets["credentials"]["usernames"][user]["email"],
            "password": st.secrets["credentials"]["usernames"][user]["password"],
            "role": st.secrets["credentials"]["usernames"][user]["role"]
        }
        for user in st.secrets["credentials"]["usernames"]
    }
}

# Initialize the authenticator
authenticator = stauth.Authenticate(
    credentials,
    "my_cookie_name",  # Define a specific cookie name for your app
    "my_signature_key",  # This should be a long random string to secure the cookie
    cookie_expiry_days=30,
    pre_authorized=None
)

authenticator.login()

st.session_state['role'] = credentials['usernames'][st.session_state['username']]['role']
st.write(st.session_state['username'])


# Custom CSS to make the watermark less conspicuous
st.markdown(
    """
    <style>
    .watermark {
        font-size: 15px;
        text-align: center;
        color: gray;
        margin-top: 3px;  # Adjust the position as needed
    }
    </style>
    """, unsafe_allow_html=True
)

# Adding the watermark to your Streamlit app
st.markdown(
    '<p class="watermark">Designed by Yanawat Pattharapistthorn and TE Group (2024).</p>',
    unsafe_allow_html=True
)

# Read reservation data from Google Sheets
df_non_pcr = conn.read(worksheet='Non_PCR', usecols=list(range(5)), ttl=10)
df_non_pcr['Start_Time'] = pd.to_datetime(df_non_pcr['Start_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')
df_non_pcr['End_Time'] = pd.to_datetime(df_non_pcr['End_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')

df_pcr = conn.read(worksheet='PCR', usecols=list(range(5)), ttl=10)
df_pcr['Start_Time'] = pd.to_datetime(df_pcr['Start_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')
df_pcr['End_Time'] = pd.to_datetime(df_pcr['End_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')

df_pcr.dropna(inplace= True)
df_non_pcr.dropna(inplace= True)

# Equipments details handling
def load_json(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def save_equipment_details(details, json_file_path='equipment_details.json'):
    with open(json_file_path, 'w') as file:
        json.dump(details, file, indent=4)

# Image handling
def image_exists(image_path):
    return os.path.exists(image_path)

def safe_display_image(image_path, width=100, offset=0):
    if image_exists(image_path):
        cols = st.columns([offset, 1])
        with cols[1]:
            st.image(image_path, width=width)
    else:
        st.error("Image not available.")

# Custom CSS
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
        font-size: 40px;
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


def convert_df_to_csv(df):
    """Converts a DataFrame to a CSV string."""
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue().encode('utf-8')

def generate_time_slots():
    slots = [{
        "label": f"Slot {i + 1}: {datetime.time(hour=h).strftime('%H:%M')}-{datetime.time(hour=h + 3).strftime('%H:%M')}",
        "start": datetime.time(hour=h), "end": datetime.time(hour=h + 3)}
        for i, h in enumerate(range(8, 20, 3))]
    return slots


slots = generate_time_slots()

# Load equipment details from JSON instead of hardcoding
room_equipment_details = load_json('equipment_details.json')

if st.session_state.get("role") == 'Admins':
    # Display reservation data from Google Sheets
    st.write(df_pcr, "PCR Equipments Reservations")
    st.write(df_non_pcr, "Non-PCR Equipments Reservations")
    st.sidebar.write("Admin Interface")
    selected_room_admin = st.sidebar.selectbox("Select a room to manage equipment:", list(room_equipment_details.keys()))
    equipment_list = list(room_equipment_details[selected_room_admin].keys())
    selected_equipment_admin = st.sidebar.selectbox("Select equipment to toggle availability:", equipment_list)

    if st.sidebar.button("Toggle Availability"):
        # Toggle equipment availability status
        current_status = room_equipment_details[selected_room_admin][selected_equipment_admin]['enabled']
        room_equipment_details[selected_room_admin][selected_equipment_admin]['enabled'] = not current_status
        # Show success message and save updated status
        st.sidebar.success(f"{'Disabled' if current_status else 'Enabled'} {selected_equipment_admin}")
        save_equipment_details(room_equipment_details)

    # Button to clear all reservation data
    if st.sidebar.button("Clear All Reservations"):
        conn.clear(worksheet="PCR")
        conn.clear(worksheet="Non_PCR")
        st.sidebar.success("All reservation data has been cleared.")

# Check if the user is authorized (either an admin or a lecturer) and allow them to post an announcement
if st.session_state["role"] in ["Admins", "Lecturer"]:
    with st.sidebar:
        st.write("Admin and Lecturer Controls")
        announcement_text = st.text_area("Enter announcement:")
        if st.button("Update Announcement"):
            st.session_state['announcement'] = announcement_text
            st.session_state['show_announcement'] = True

# Always check if there's an announcement to display
if 'show_announcement' in st.session_state and st.session_state['show_announcement']:
    # Using st.markdown to insert HTML for a moving text effect
    st.markdown(
        f"<marquee style='width: 100%; color: red; font-size: 24px;'>{st.session_state['announcement']}</marquee>",
        unsafe_allow_html=True
    )

# Usual app interface
if st.session_state["authentication_status"]:
    authenticator.logout(location='sidebar')
    message = f"## Welcome <span class='welcome-message'>{st.session_state['name']}</span>"
    st.markdown(message, unsafe_allow_html=True)
    tab1, tab2, tab3, tab4 = st.tabs(["Reservation Tables", "Reservation Forms", "Reservation Cancellation", "Contact Us"])

    # Adding download buttons in the sidebar for each DataFrame
    st.sidebar.download_button(
        label="Download General Reservations as CSV",
        data=convert_df_to_csv(df_non_pcr),
        file_name='general_reservations.csv',
        mime='text/csv'
    )

    st.sidebar.download_button(
        label="Download PCR Reservations as CSV",
        data=convert_df_to_csv(df_pcr),
        file_name='pcr_reservations.csv',
        mime='text/csv'
    )

    with tab1:
        room_selection = st.selectbox("### Select a Room", list(room_equipment_details.keys()), key='tab1 select room')

        # Generate a list of dates for the next week
        dates = [(datetime.date.today() + datetime.timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        view_date = st.selectbox("### View reservations for", dates)
        selected_date = datetime.datetime.strptime(view_date, '%Y-%m-%d').date()

        full_day_start = datetime.datetime.combine(selected_date, datetime.time(0, 0))
        full_day_end = datetime.datetime.combine(selected_date, datetime.time(23, 59))
        pcr_start = datetime.datetime.combine(selected_date, datetime.time(8, 0))
        pcr_end = datetime.datetime.combine(selected_date, datetime.time(20, 0))

        # Filter DataFrames for the selected day
        df_pcr_filtered = df_pcr[(df_pcr['Room'] == room_selection) & (df_pcr['Start_Time'].dt.date == selected_date)]
        df_non_pcr_filtered = df_non_pcr[
            (df_non_pcr['Room'] == room_selection) & (df_non_pcr['Start_Time'].dt.date == selected_date)]

        gantt_df_list_pcr = []
        gantt_df_list_non_pcr = []

        for equipment, details in room_equipment_details[room_selection].items():
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
        selected_room = st.selectbox("### Select a Room", list(room_equipment_details.keys()))

        # Equipments selection based on the selected room
        selected_equipment = st.selectbox("### Select Equipments",
                                          list(room_equipment_details[selected_room].keys()))

        # Fetch equipment information
        equipment_info = room_equipment_details[selected_room][selected_equipment]

        # Display selected equipment details and image
        safe_display_image(equipment_info['image'], width=450, offset=0.5)  # Adjust width as necessary
        st.write(f"#### Details : {equipment_info['details']}")

        # Check if equipment is enabled before allowing reservation
        if equipment_info.get('enabled', True):  # Proceed if equipment is enabled
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
                    df_pcr = conn.read(worksheet='PCR', usecols=list(range(5)), ttl=10)
                    df_pcr.dropna(inplace=True)
                    df_pcr['Start_Time'] = pd.to_datetime(df_pcr['Start_Time'], format='%Y/%m/%d %H:%M:%S',
                                                          errors='coerce')
                    df_pcr['End_Time'] = pd.to_datetime(df_pcr['End_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')

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

                        # Update the Google Sheet with the new buffer DataFrame
                        conn.update(worksheet="PCR", data=df_pcr_buffer)

                        st.success(
                            f"Reservation successful for {selected_equipment} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")



            else:

                if "PCR" not in selected_equipment:

                    st.subheader(f"Reserve {selected_equipment}")

                    # Set the maximum days in advance based on the equipment type
                    max_days_advance = 1 if "Autoclave" in selected_equipment else 7
                    max_date = datetime.date.today() + datetime.timedelta(days=max_days_advance)

                    start_date = st.date_input("## Start Date", min_value=datetime.date.today(), max_value=max_date)

                    current_time = datetime.datetime.now().replace(second=0, microsecond=0)
                    # Set minimum time for the start time input based on whether the reservation date is today
                    min_time = current_time.time() if start_date == datetime.date.today() else datetime.time(0, 0)

                    start_time = st.time_input("## Start Time", value=min_time)
                    end_time = st.time_input("## End Time",
                                             value=(current_time + datetime.timedelta(
                                                 hours=1)).time() if start_date == datetime.date.today() else datetime.time(
                                                 1, 0))

                    start_datetime = datetime.datetime.combine(start_date, start_time)
                    end_datetime = datetime.datetime.combine(start_date, end_time)

                    if st.button("### Submit Reservation"):
                        if start_datetime < current_time:
                            st.error("Cannot book a reservation in the past. Please select a future time.")
                        elif start_datetime >= end_datetime:
                            st.error("The start time must be before the end time. Please adjust your selection.")
                        else:
                            # Assuming df_non_pcr is already loaded and filtered as needed
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

                                conn.update(worksheet="Non_PCR", data=df_non_pcr_buffer)

                                st.success(
                                    f"Reservation successful for {selected_equipment} in {selected_room} from {start_datetime.strftime('%Y/%m/%d %H:%M:%S')} to {end_datetime.strftime('%Y/%m/%d %H:%M:%S')}")
        else:
            st.error("This equipment is currently not available for reservation.")

    with tab3:
        # st.subheader("Reservation Cancellation")

        df_non_pcr = conn.read(worksheet='Non_PCR', usecols=list(range(5)), ttl=10)
        df_non_pcr.dropna(inplace=True)
        df_non_pcr['Start_Time'] = pd.to_datetime(df_non_pcr['Start_Time'], format='%Y/%m/%d %H:%M:%S',
                                                  errors='coerce')
        df_non_pcr['End_Time'] = pd.to_datetime(df_non_pcr['End_Time'], format='%Y/%m/%d %H:%M:%S',
                                                errors='coerce')

        df_pcr = conn.read(worksheet='PCR', usecols=list(range(5)), ttl=10)
        df_pcr.dropna(inplace=True)
        df_pcr['Start_Time'] = pd.to_datetime(df_pcr['Start_Time'], format='%Y/%m/%d %H:%M:%S',
                                              errors='coerce')
        df_pcr['End_Time'] = pd.to_datetime(df_pcr['End_Time'], format='%Y/%m/%d %H:%M:%S', errors='coerce')

        # Combining both dataframes to get user-specific reservations
        user_reservations_pcr = df_pcr[df_pcr['Name'] == st.session_state["name"]]
        user_reservations_non_pcr = df_non_pcr[df_non_pcr['Name'] == st.session_state["name"]]
        user_reservations = pd.concat([user_reservations_pcr, user_reservations_non_pcr])

        # Current datetime and 30 minutes before now
        current_datetime = datetime.datetime.now()

        # Current date and tomorrow's date for filtering
        today = datetime.date.today()
        tomorrow = today + datetime.timedelta(days=1)

        # Filter the DataFrame to only include reservations for today and tomorrow
        user_reservations = user_reservations[
            (user_reservations['Start_Time'].dt.date.isin([today, tomorrow])) &
            (user_reservations['Start_Time'] > current_datetime)
            ]

        if not user_reservations.empty:
            # Display the reservations in a selectbox
            selected_reservation_index = st.selectbox(
                "## Your Reservations:",
                options=range(len(user_reservations)),
                format_func=lambda x: f"{user_reservations.iloc[x]['Equipments']} on " +
                                      (user_reservations.iloc[x]['Start_Time'].strftime('%Y/%m/%d %H:%M:%S') + ' To ' + user_reservations.iloc[x]['End_Time'].strftime('%Y/%m/%d %H:%M:%S') if pd.notnull(
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
                    conn.update(worksheet="PCR", data=df_pcr)  # Writing updated dataframe back
                else:
                    df_non_pcr.drop(index=reservation_to_cancel.name, inplace=True)
                    df_non_pcr['Start_Time'] = df_non_pcr['Start_Time'].dt.strftime(
                        '%Y/%m/%d %H:%M:%S')
                    df_non_pcr['End_Time'] = df_non_pcr['End_Time'].dt.strftime(
                        '%Y/%m/%d %H:%M:%S')
                    conn.update(worksheet="Non_PCR", data=df_non_pcr)  # Writing updated dataframe back

                st.success("Reservation canceled successfully.")

        else:
            st.write("## You have no reservations.")

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


        # Use Local CSS File
        def local_css(file_name):
            with open(file_name) as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


        local_css("style.css")


elif st.session_state["authentication_status"] is False:
    st.error('Name/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password')
