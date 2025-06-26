from telethon.sync import TelegramClient, events
from transformers import pipeline
import re

# Step 1: Fill in your credentials
api_id =  20581631         # Replace with your actual API ID
api_hash = 'e048725183f82fe4e8e4e826549edc88'    # Replace with your actual API Hash
group_name = 'Engineering 2026 batch'  # Replace with your actual group title

# Step 2: Load the NLP summarizer
summarizer = pipeline("summarization", model="t5-small")

# Step 3: Utility functions
def extract_links(text):
    return re.findall(r'(https?://[^\s]+)', text)

def classify_message(text):
    text = text.lower()
    if 'hackathon' in text:
        return '🏆 Hackathon'
    elif 'campus drive' in text or 'recruitment' in text or 'apply here' in text:
        return '📌 Placement'
    elif 'test link' in text or 'talview' in text or 'online test' in text:
        return '🧪 Test/Exam Update'
    elif 'internal process' in text or 'college link' in text:
        return '🏫 College Process'
    elif 'email id' in text or 'wrong email' in text:
        return '⚠️ Error Warning'
    else:
        return '📄 General Info'

def extract_degree_branch_campus(text):
    degree = 'M.Tech' if 'm.tech' in text.lower() else 'B.Tech'
    
    branches = []
    if 'cse' in text.lower(): branches.append('CSE')
    if 'ece' in text.lower(): branches.append('ECE')
    if 'eee' in text.lower(): branches.append('EEE')
    if 'mech' in text.lower(): branches.append('Mech')
    if 'civil' in text.lower(): branches.append('Civil')
    if 'chemical' in text.lower(): branches.append('Chemical')
    if 'it' in text.lower(): branches.append('IT')

    campus = []
    if 'dsce' in text.lower(): campus.append('DSCE')
    if 'dsatm' in text.lower(): campus.append('DSATM')
    if 'dsu' in text.lower(): campus.append('DSU')

    return degree, branches, campus

def extract_deadline(text):
    match = re.search(r'(on or before|by)\s([\w\s:\/]+)', text.lower())
    return match.group(0).strip().capitalize() if match else None

def get_summary(text):
    try:
        result = summarizer(text, max_length=80, min_length=30, do_sample=False)
        return result[0]['summary_text']
    except:
        return text[:150]  # fallback

# Step 4: Initialize the client
client = TelegramClient('session_name', api_id, api_hash)

@client.on(events.NewMessage)
async def handler(event):
    if event.chat and group_name.lower() in event.chat.title.lower():
        text = event.raw_text
        if len(text.strip()) == 0:
            return

        category = classify_message(text)
        degree, branches, campuses = extract_degree_branch_campus(text)
        links = extract_links(text)
        deadline = extract_deadline(text)
        summary = get_summary(text)

        response = f"{category} Alert!\n"
        response += f"\n🎓 Degree: {degree}\n"
        if branches:
            response += f"🧑‍💻 Branches: {', '.join(branches)}\n"
        if campuses:
            response += f"🏫 Campus: {', '.join(campuses)}\n"
        if deadline:
            response += f"📅 Deadline: {deadline}\n"
        response += f"\n📝 Summary:\n{summary}\n"
        if links:
            response += "\n🔗 Links:\n" + "\n".join(links)

        print("\n" + "="*50 + "\n" + response + "\n" + "="*50)

# Step 5: Start the client
with client:
    print("🔄 Listening to messages...")
    client.run_until_disconnected()