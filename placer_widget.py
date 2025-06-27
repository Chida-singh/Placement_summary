import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from datetime import datetime, timedelta
import threading
from telethon.sync import TelegramClient, events
from transformers import pipeline
import re
import asyncio

# Base directory (folder where .py or .exe is located)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_FILE = os.path.join(BASE_DIR, "latest_summary.txt")
DEADLINE_FILE = os.path.join(BASE_DIR, "deadlines.json")
EVENTS_FILE = os.path.join(BASE_DIR, "events.json")
APPLICATIONS_FILE = os.path.join(BASE_DIR, "applications.json")

# Telegram Configuration
api_id = 20581631
api_hash = 'e048725183f82fe4e8e4e826549edc88'
group_name = 'Engineering 2026 batch'

# UI refresh interval (in milliseconds)
AUTO_REFRESH_INTERVAL = 30 * 60 * 1000  # 30 mins

class PlacementWidget:
    def __init__(self, root):
        self.root = root
        self.setup_ui()
        self.telegram_running = False
        self.client = None
        self.summarizer = None
        self.load_data()
        
    def setup_ui(self):
        self.root.title("📢 Placement & Events Tracker")
        self.root.geometry("700x600+50+50")
        self.root.configure(bg="#f8f9fa")
        
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="🎓 Placement & Events Dashboard", 
                              font=("Helvetica", 16, "bold"), bg="#f8f9fa", fg="#2c3e50")
        title_label.pack(pady=(0, 10))
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(control_frame, text="🔄 Refresh All", 
                  command=self.refresh_all_data).pack(side="left", padx=5)
        
        self.telegram_btn = ttk.Button(control_frame, text="🤖 Start Telegram Monitor", 
                                      command=self.toggle_telegram)
        self.telegram_btn.pack(side="left", padx=5)
        
        self.history_btn = ttk.Button(control_frame, text="📜 Scan Message History", 
                                     command=self.scan_message_history)
        self.history_btn.pack(side="left", padx=5)
        
        ttk.Button(control_frame, text="🗕 Minimize", 
                  command=self.root.iconify).pack(side="right", padx=5)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="Status: Ready", 
                                   font=("Helvetica", 9), bg="#f8f9fa", fg="#7f8c8d")
        self.status_label.pack(anchor="w", pady=(0, 10))
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)
        
        # Tab 1: Latest Updates
        self.create_updates_tab()
        
        # Tab 2: Deadlines
        self.create_deadlines_tab()
        
        # Tab 3: Events & Hackathons
        self.create_events_tab()
        
        # Tab 4: Application Tracker
        self.create_applications_tab()
        
    def create_updates_tab(self):
        updates_frame = ttk.Frame(self.notebook)
        self.notebook.add(updates_frame, text="📋 Latest Updates")
        
        # History scanning section
        history_frame = ttk.LabelFrame(updates_frame, text="Message History Scanner", padding=10)
        history_frame.pack(fill="x", padx=5, pady=5)
        
        # History controls
        hist_control_frame = ttk.Frame(history_frame)
        hist_control_frame.pack(fill="x")
        
        tk.Label(hist_control_frame, text="Scan last:").pack(side="left", padx=5)
        
        self.history_days = tk.StringVar(value="7")
        ttk.Combobox(hist_control_frame, textvariable=self.history_days, 
                    values=["1", "3", "7", "14", "30"], width=5).pack(side="left", padx=5)
        
        tk.Label(hist_control_frame, text="days").pack(side="left", padx=5)
        
        self.history_progress = ttk.Progressbar(hist_control_frame, mode='indeterminate')
        self.history_progress.pack(side="left", padx=10, fill="x", expand=True)
        
        # History results
        tk.Label(history_frame, text="Scan Results:").pack(anchor="w", pady=(10, 0))
        self.history_results = scrolledtext.ScrolledText(history_frame, height=6, wrap=tk.WORD,
                                                        font=("Consolas", 9))
        self.history_results.pack(fill="x", pady=5)
        
        # Summary section
        tk.Label(updates_frame, text="Latest Summary", 
                font=("Helvetica", 11, "bold")).pack(pady=(10, 5), anchor="w")
        
        self.summary_text = scrolledtext.ScrolledText(updates_frame, height=20, wrap=tk.WORD,
                                                     font=("Consolas", 9))
        self.summary_text.pack(fill="both", expand=True, padx=5, pady=5)
        
    def create_deadlines_tab(self):
        deadlines_frame = ttk.Frame(self.notebook)
        self.notebook.add(deadlines_frame, text="📅 Deadlines")
        
        # Filter frame
        filter_frame = ttk.Frame(deadlines_frame)
        filter_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(filter_frame, text="Show:").pack(side="left", padx=5)
        
        self.deadline_filter = tk.StringVar(value="upcoming")
        ttk.Radiobutton(filter_frame, text="Upcoming", variable=self.deadline_filter, 
                       value="upcoming", command=self.filter_deadlines).pack(side="left", padx=5)
        ttk.Radiobutton(filter_frame, text="This Week", variable=self.deadline_filter, 
                       value="week", command=self.filter_deadlines).pack(side="left", padx=5)
        ttk.Radiobutton(filter_frame, text="All", variable=self.deadline_filter, 
                       value="all", command=self.filter_deadlines).pack(side="left", padx=5)
        
        # Deadlines list
        self.deadlines_text = scrolledtext.ScrolledText(deadlines_frame, height=18, wrap=tk.WORD,
                                                       font=("Consolas", 9))
        self.deadlines_text.pack(fill="both", expand=True, padx=5, pady=5)
        
    def create_events_tab(self):
        events_frame = ttk.Frame(self.notebook)
        self.notebook.add(events_frame, text="🏆 Events & Hackathons")
        
        # Events list
        self.events_text = scrolledtext.ScrolledText(events_frame, height=20, wrap=tk.WORD,
                                                    font=("Consolas", 9))
        self.events_text.pack(fill="both", expand=True, padx=5, pady=5)
        
    def create_applications_tab(self):
        applications_frame = ttk.Frame(self.notebook)
        self.notebook.add(applications_frame, text="✅ Application Tracker")
        
        # Add application frame
        add_frame = ttk.LabelFrame(applications_frame, text="Add New Application", padding=10)
        add_frame.pack(fill="x", padx=5, pady=5)
        
        # Entry fields
        entry_frame = ttk.Frame(add_frame)
        entry_frame.pack(fill="x")
        
        tk.Label(entry_frame, text="Company:").grid(row=0, column=0, sticky="w", padx=5)
        self.company_entry = ttk.Entry(entry_frame, width=20)
        self.company_entry.grid(row=0, column=1, padx=5, pady=2)
        
        tk.Label(entry_frame, text="Position:").grid(row=0, column=2, sticky="w", padx=5)
        self.position_entry = ttk.Entry(entry_frame, width=20)
        self.position_entry.grid(row=0, column=3, padx=5, pady=2)
        
        tk.Label(entry_frame, text="Deadline:").grid(row=1, column=0, sticky="w", padx=5)
        self.deadline_entry = ttk.Entry(entry_frame, width=20)
        self.deadline_entry.grid(row=1, column=1, padx=5, pady=2)
        
        tk.Label(entry_frame, text="Status:").grid(row=1, column=2, sticky="w", padx=5)
        self.status_var = tk.StringVar(value="Not Applied")
        status_combo = ttk.Combobox(entry_frame, textvariable=self.status_var, 
                                   values=["Not Applied", "Applied", "Test Scheduled", "Interview Scheduled", "Completed"])
        status_combo.grid(row=1, column=3, padx=5, pady=2)
        
        ttk.Button(add_frame, text="➕ Add Application", 
                  command=self.add_application).pack(pady=10)
        
        # Applications list
        list_frame = ttk.LabelFrame(applications_frame, text="Your Applications", padding=5)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Treeview for applications
        columns = ("Company", "Position", "Deadline", "Status", "Added")
        self.app_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        
        for col in columns:
            self.app_tree.heading(col, text=col)
            self.app_tree.column(col, width=120)
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=scrollbar.set)
        
        self.app_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Context menu for applications
        self.app_tree.bind("<Button-3>", self.show_context_menu)
        
        # Buttons frame
        btn_frame = ttk.Frame(applications_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(btn_frame, text="🗑️ Delete Selected", 
                  command=self.delete_application).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="✏️ Edit Status", 
                  command=self.edit_application_status).pack(side="left", padx=5)
        
    def load_data(self):
        """Load all data from files"""
        self.refresh_all_data()
        # Schedule automatic refresh
        self.root.after(AUTO_REFRESH_INTERVAL, self.load_data)
        
    def refresh_all_data(self):
        """Refresh all tabs with latest data"""
        self.update_status("Refreshing data...")
        
        # Update summary
        summary = self.read_summary()
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, summary)
        
        # Update deadlines
        self.filter_deadlines()
        
        # Update events
        self.refresh_events()
        
        # Update applications
        self.refresh_applications()
        
        self.update_status("Data refreshed successfully")
        
    def read_summary(self):
        """Read the latest summary from file"""
        try:
            with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return "No recent summary available.\n\nTo get started:\n1. Click 'Start Telegram Monitor' to begin monitoring\n2. Messages from your group will appear here automatically"
    
    def filter_deadlines(self):
        """Filter and display deadlines based on selected filter"""
        try:
            with open(DEADLINE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
        
        now = datetime.now()
        week_from_now = now + timedelta(days=7)
        
        # Filter based on selection
        filter_type = self.deadline_filter.get()
        if filter_type == "upcoming":
            filtered_data = [d for d in data if datetime.strptime(d['deadline'], "%Y-%m-%d %H:%M") > now]
        elif filter_type == "week":
            filtered_data = [d for d in data if now < datetime.strptime(d['deadline'], "%Y-%m-%d %H:%M") <= week_from_now]
        else:  # all
            filtered_data = data
        
        # Sort by deadline
        filtered_data = sorted(filtered_data, key=lambda x: x['deadline'])
        
        # Display
        self.deadlines_text.delete(1.0, tk.END)
        if filtered_data:
            for item in filtered_data:
                deadline_dt = datetime.strptime(item['deadline'], "%Y-%m-%d %H:%M")
                time_left = deadline_dt - now
                
                if time_left.days > 0:
                    time_str = f"({time_left.days} days left)"
                elif time_left.total_seconds() > 0:
                    hours = int(time_left.total_seconds() // 3600)
                    time_str = f"({hours} hours left)"
                else:
                    time_str = "⚠️ EXPIRED"
                
                self.deadlines_text.insert(tk.END, f"📌 {item['title']}\n")
                self.deadlines_text.insert(tk.END, f"🕒 {deadline_dt.strftime('%d/%m/%Y %I:%M %p')} {time_str}\n\n")
        else:
            self.deadlines_text.insert(tk.END, f"No deadlines found for '{filter_type}' filter.")
    
    def refresh_events(self):
        """Refresh events and hackathons"""
        try:
            with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except:
            events = []
        
        self.events_text.delete(1.0, tk.END)
        if events:
            for event in events:
                self.events_text.insert(tk.END, f"🏆 {event.get('title', 'Event')}\n")
                self.events_text.insert(tk.END, f"📅 {event.get('date', 'Date TBD')}\n")
                if event.get('description'):
                    self.events_text.insert(tk.END, f"📝 {event['description']}\n")
                if event.get('link'):
                    self.events_text.insert(tk.END, f"🔗 {event['link']}\n")
                self.events_text.insert(tk.END, "\n" + "-"*50 + "\n\n")
        else:
            self.events_text.insert(tk.END, "No events or hackathons found.\n\nEvents will appear here automatically when detected from Telegram messages.")
    
    def add_application(self):
        """Add a new application to tracker"""
        company = self.company_entry.get().strip()
        position = self.position_entry.get().strip()
        deadline = self.deadline_entry.get().strip()
        status = self.status_var.get()
        
        if not company or not position:
            messagebox.showerror("Error", "Company and Position are required!")
            return
        
        # Load existing applications
        try:
            with open(APPLICATIONS_FILE, 'r', encoding='utf-8') as f:
                applications = json.load(f)
        except:
            applications = []
        
        # Add new application
        new_app = {
            "id": len(applications) + 1,
            "company": company,
            "position": position,
            "deadline": deadline,
            "status": status,
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        applications.append(new_app)
        
        # Save to file
        with open(APPLICATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(applications, f, indent=2, ensure_ascii=False)
        
        # Clear entries
        self.company_entry.delete(0, tk.END)
        self.position_entry.delete(0, tk.END)
        self.deadline_entry.delete(0, tk.END)
        self.status_var.set("Not Applied")
        
        # Refresh display
        self.refresh_applications()
        
        self.update_status(f"Added application: {company} - {position}")
    
    def refresh_applications(self):
        """Refresh the applications treeview"""
        # Clear existing items
        for item in self.app_tree.get_children():
            self.app_tree.delete(item)
        
        # Load applications
        try:
            with open(APPLICATIONS_FILE, 'r', encoding='utf-8') as f:
                applications = json.load(f)
        except:
            applications = []
        
        # Sort by added date (newest first)
        applications = sorted(applications, key=lambda x: x.get('added_date', ''), reverse=True)
        
        # Add to treeview
        for app in applications:
            self.app_tree.insert("", "end", values=(
                app.get('company', ''),
                app.get('position', ''),
                app.get('deadline', ''),
                app.get('status', ''),
                app.get('added_date', '').split()[0]  # Just the date part
            ), tags=(app.get('id'),))
    
    def delete_application(self):
        """Delete selected application"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to delete!")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this application?"):
            # Get app ID from tags
            item = selected[0]
            app_id = self.app_tree.item(item, 'tags')[0]
            
            # Load applications
            try:
                with open(APPLICATIONS_FILE, 'r', encoding='utf-8') as f:
                    applications = json.load(f)
            except:
                applications = []
            
            # Remove application
            applications = [app for app in applications if str(app.get('id')) != str(app_id)]
            
            # Save back
            with open(APPLICATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(applications, f, indent=2, ensure_ascii=False)
            
            # Refresh display
            self.refresh_applications()
            self.update_status("Application deleted")
    
    def edit_application_status(self):
        """Edit the status of selected application"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an application to edit!")
            return
        
        # Get current status
        item = selected[0]
        current_status = self.app_tree.item(item, 'values')[3]
        app_id = self.app_tree.item(item, 'tags')[0]
        
        # Create dialog for status change
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Status")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Select new status:").pack(pady=10)
        
        status_var = tk.StringVar(value=current_status)
        statuses = ["Not Applied", "Applied", "Test Scheduled", "Interview Scheduled", "Completed", "Rejected"]
        
        for status in statuses:
            ttk.Radiobutton(dialog, text=status, variable=status_var, value=status).pack(anchor="w", padx=20)
        
        def update_status():
            new_status = status_var.get()
            
            # Load applications
            try:
                with open(APPLICATIONS_FILE, 'r', encoding='utf-8') as f:
                    applications = json.load(f)
            except:
                applications = []
            
            # Update status
            for app in applications:
                if str(app.get('id')) == str(app_id):
                    app['status'] = new_status
                    break
            
            # Save back
            with open(APPLICATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(applications, f, indent=2, ensure_ascii=False)
            
            # Refresh display
            self.refresh_applications()
            self.update_status(f"Status updated to: {new_status}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Update", command=update_status).pack(pady=20)
    
    def show_context_menu(self, event):
        """Show context menu for applications"""
        item = self.app_tree.identify_row(event.y)
        if item:
            self.app_tree.selection_set(item)
            
            context_menu = tk.Menu(self.root, tearoff=0)
            context_menu.add_command(label="Edit Status", command=self.edit_application_status)
            context_menu.add_command(label="Delete", command=self.delete_application)
            
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
    
    def scan_message_history(self):
        """Scan previous messages from Telegram group"""
        if self.telegram_running:
            messagebox.showwarning("Warning", "Please stop Telegram monitoring before scanning history.")
            return
            
        # Get number of days to scan
        try:
            days = int(self.history_days.get())
        except:
            days = 7
            
        # Ask for confirmation
        if not messagebox.askyesno("Confirm History Scan", 
                                  f"This will scan the last {days} days of messages from '{group_name}'.\n\n"
                                  f"This may take a few minutes depending on message volume.\n\n"
                                  f"Continue?"):
            return
            
        # Start scanning in background thread
        self.history_btn.configure(state="disabled", text="📜 Scanning...")
        self.history_progress.start(10)
        self.history_results.delete(1.0, tk.END)
        self.history_results.insert(tk.END, "Starting message history scan...\n")
        
        threading.Thread(target=self.run_history_scan, args=(days,), daemon=True).start()
    
    def run_history_scan(self, days):
        """Run the actual history scan in background"""
        scan_client = None
        try:
            from datetime import timedelta
            
            # Initialize client for history scanning
            scan_client = TelegramClient('history_session', api_id, api_hash)
            
            with scan_client:
                # Get the group
                group = None
                
                # Find group synchronously
                for dialog in scan_client.iter_dialogs():
                    if dialog.is_group and group_name.lower() in dialog.name.lower():
                        group = dialog.entity
                        break
                
                if not group:
                    self.root.after(0, lambda: self.history_scan_complete("❌ Group not found!", []))
                    return
                
                # Calculate date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                
                # Scan messages with optimization
                messages_found = []
                processed_count = 0
                relevant_keywords = [
                    'placement', 'recruitment', 'hiring', 'job', 'interview',
                    'hackathon', 'competition', 'contest', 'apply', 
                    'deadline', 'last date', 'campus drive', 'company',
                    'test link', 'online test', 'assessment', 'registration',
                    'internship', 'opportunity', 'eligible', 'register'
                ]
                
                # Batch process messages for better performance
                batch_size = 50
                message_batch = []
                
                for message in scan_client.iter_messages(group, offset_date=start_date, limit=None):
                    if message.date < start_date:
                        break
                        
                    if message.text and len(message.text.strip()) > 20:  # Filter very short messages
                        processed_count += 1
                        message_batch.append(message)
                        
                        # Process batch
                        if len(message_batch) >= batch_size:
                            relevant_messages = self.process_message_batch(message_batch, relevant_keywords)
                            messages_found.extend(relevant_messages)
                            message_batch = []
                            
                            # Update progress
                            progress_msg = f"Processed {processed_count} messages, found {len(messages_found)} relevant..."
                            self.root.after(0, lambda msg=progress_msg: self.update_history_progress(msg))
                
                # Process remaining messages in batch
                if message_batch:
                    relevant_messages = self.process_message_batch(message_batch, relevant_keywords)
                    messages_found.extend(relevant_messages)
                
                # Process found messages
                self.root.after(0, lambda: self.process_history_results(messages_found, processed_count))
                
        except Exception as e:
            error_msg = f"❌ Error during scan: {str(e)}"
            self.root.after(0, lambda: self.history_scan_complete(error_msg, []))
        finally:
            if scan_client:
                try:
                    scan_client.disconnect()
                except:
                    pass
    
    def process_message_batch(self, message_batch, relevant_keywords):
        """Process a batch of messages for relevant content"""
        relevant_messages = []
        
        for message in message_batch:
            text = message.text.lower()
            
            # Quick keyword check
            if any(keyword in text for keyword in relevant_keywords):
                # Additional relevance scoring
                relevance_score = sum(1 for keyword in relevant_keywords if keyword in text)
                
                # Only include messages with high relevance or containing multiple keywords
                if relevance_score >= 1 or any(important in text for important in ['deadline', 'apply', 'registration', 'hiring']):
                    relevant_messages.append({
                        'text': message.text,
                        'date': message.date.strftime("%Y-%m-%d %H:%M"),
                        'id': message.id,
                        'relevance': relevance_score
                    })
        
        return relevant_messages
    
    def update_history_progress(self, message):
        """Update history scan progress"""
        self.history_results.insert(tk.END, f"{message}\n")
        self.history_results.see(tk.END)
        self.root.update_idletasks()
    
    def process_history_results(self, messages_found, total_processed):
        """Process the results from history scan with better performance"""
        try:
            # Sort messages by relevance score (if available) and date
            messages_found.sort(key=lambda x: (x.get('relevance', 0), x['date']), reverse=True)
            
            # Load existing data to avoid duplicates
            existing_deadlines = set()
            existing_events = set()
            
            try:
                with open(DEADLINE_FILE, 'r', encoding='utf-8') as f:
                    deadlines = json.load(f)
                    existing_deadlines = set(d['title'][:50] for d in deadlines)  # Use first 50 chars for comparison
            except:
                pass
                
            try:
                with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                    events = json.load(f)
                    existing_events = set(e['title'][:50] for e in events)
            except:
                pass
            
            new_deadlines = 0
            new_events = 0
            all_summaries = []
            
            # Process messages in batches for better performance
            batch_size = 10
            for i in range(0, len(messages_found), batch_size):
                batch = messages_found[i:i+batch_size]
                
                # Update progress
                progress = f"Processing batch {i//batch_size + 1}/{(len(messages_found)-1)//batch_size + 1}..."
                self.root.after(0, lambda msg=progress: self.update_history_progress(msg))
                
                for msg in batch:
                    text = msg['text']
                    
                    # Extract information
                    category = self.classify_message(text)
                    deadline = self.extract_deadline(text)
                    summary = self.get_summary(text)
                    links = self.extract_links(text)
                    
                    # Create summary entry
                    all_summaries.append(f"[{msg['date']}] {category}\n{summary[:100]}{'...' if len(summary) > 100 else ''}\n{'-'*40}")
                    
                    # Check for duplicates using truncated summary
                    summary_key = summary[:50]
                    
                    # Save deadline if found and not duplicate
                    if deadline and summary_key not in existing_deadlines:
                        try:
                            self.save_deadline_summary(summary, deadline)
                            existing_deadlines.add(summary_key)
                            new_deadlines += 1
                        except:
                            pass  # Skip if deadline parsing fails
                    
                    # Save event if it's a hackathon and not duplicate
                    if 'hackathon' in text.lower() and summary_key not in existing_events:
                        try:
                            self.save_event(summary, deadline, links)
                            existing_events.add(summary_key)
                            new_events += 1
                        except:
                            pass  # Skip if event saving fails
            
            # Create comprehensive summary (limit to prevent memory issues)
            summary_preview = all_summaries[:15]  # Show top 15 instead of 10
            
            history_summary = f"""📊 HISTORY SCAN RESULTS ({self.history_days.get()} days):

📈 Total messages processed: {total_processed}
🎯 Relevant messages found: {len(messages_found)}
📅 New deadlines added: {new_deadlines}
🏆 New events added: {new_events}
⭐ Scan completed at: {datetime.now().strftime("%Y-%m-%d %H:%M")}

📋 MOST RELEVANT MESSAGES:
{chr(10).join(summary_preview)}

""" + (f"📌 {len(messages_found) - 15} more messages found. Check individual tabs for complete data." if len(messages_found) > 15 else "✅ All relevant messages shown above.")
            
            # Save comprehensive summary
            with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
                f.write(history_summary)
            
            # Complete the scan
            result_msg = f"✅ Scan completed! Found {len(messages_found)} relevant messages. Added {new_deadlines} deadlines and {new_events} events."
            self.history_scan_complete(result_msg, messages_found[:10])  # Show top 10 in results
            
            # Refresh all data
            self.refresh_all_data()
            
        except Exception as e:
            error_msg = f"❌ Error processing results: {str(e)}"
            self.history_scan_complete(error_msg, [])
    
    def history_scan_complete(self, message, results):
        """Complete the history scan process"""
        self.history_progress.stop()
        self.history_btn.configure(state="normal", text="📜 Scan Message History")
        
        # Show results
        self.history_results.insert(tk.END, f"\n{message}\n")
        
        if results:
            self.history_results.insert(tk.END, f"\nMost recent relevant messages:\n")
            for i, msg in enumerate(results[:5]):  # Show top 5
                date_str = msg['date']
                preview = msg['text'][:100] + "..." if len(msg['text']) > 100 else msg['text']
                self.history_results.insert(tk.END, f"{i+1}. [{date_str}] {preview}\n\n")
        
        self.history_results.see(tk.END)
        self.update_status("History scan completed")
    
    def toggle_telegram(self):
        """Start/Stop Telegram monitoring"""
        if not self.telegram_running:
            self.start_telegram_monitoring()
        else:
            self.stop_telegram_monitoring()
    
    def start_telegram_monitoring(self):
        """Start Telegram monitoring in a separate thread"""
        try:
            # Load summarizer in background
            threading.Thread(target=self.load_summarizer, daemon=True).start()
            
            # Start Telegram client
            threading.Thread(target=self.run_telegram_client, daemon=True).start()
            
            self.telegram_running = True
            self.telegram_btn.configure(text="🛑 Stop Telegram Monitor")
            self.update_status("Telegram monitoring started...")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Telegram monitoring: {str(e)}")
    
    def stop_telegram_monitoring(self):
        """Stop Telegram monitoring"""
        self.telegram_running = False
        if self.client:
            self.client.disconnect()
        self.telegram_btn.configure(text="🤖 Start Telegram Monitor")
        self.update_status("Telegram monitoring stopped")
    
    def load_summarizer(self):
        """Load the summarizer model with GPU support"""
        try:
            import torch
            from transformers import pipeline
            
            # Check for GPU availability
            device = 0 if torch.cuda.is_available() else -1
            device_name = "GPU" if device == 0 else "CPU"
            
            self.update_status(f"Loading AI summarizer on {device_name}...")
            
            # Load with optimized settings
            self.summarizer = pipeline(
                "summarization", 
                model="t5-small",
                device=device,
                torch_dtype=torch.float16 if device == 0 else torch.float32,
                model_kwargs={"low_cpu_mem_usage": True} if device == -1 else {}
            )
            
            self.update_status(f"✅ AI summarizer loaded successfully on {device_name}")
            
        except Exception as e:
            self.update_status(f"⚠️ Could not load summarizer: {str(e)}")
            self.summarizer = None
    
    def run_telegram_client(self):
        """Run the Telegram client"""
        try:
            self.client = TelegramClient('session_name', api_id, api_hash)
            
            @self.client.on(events.NewMessage)
            async def handler(event):
                if event.chat and group_name.lower() in event.chat.title.lower():
                    text = event.raw_text.strip()
                    if not text:
                        return
                    
                    # Process message
                    self.process_telegram_message(text)
            
            with self.client:
                self.client.run_until_disconnected()
                
        except Exception as e:
            self.update_status(f"Telegram error: {str(e)}")
    
    def process_telegram_message(self, text):
        """Process incoming Telegram message"""
        try:
            category = self.classify_message(text)
            degree, branches, campuses = self.extract_degree_branch_campus(text)
            links = self.extract_links(text)
            deadline = self.extract_deadline(text)
            summary = self.get_summary(text)

            response = f"{category} Alert!\n\n🎓 Degree: {degree}\n"
            if branches:
                response += f"🧑‍💻 Branches: {', '.join(branches)}\n"
            if campuses:
                response += f"🏫 Campus: {', '.join(campuses)}\n"
            if deadline:
                response += f"📅 Deadline: {deadline}\n"
            response += f"\n📝 Summary:\n{summary}\n"
            if links:
                response += "\n🔗 Links:\n" + "\n".join(links)

            # Save to file
            with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
                f.write(response)

            # Save deadline if found
            if deadline:
                self.save_deadline_summary(summary, deadline)
            
            # Save event if it's a hackathon
            if 'hackathon' in text.lower():
                self.save_event(summary, deadline, links)
            
            # Update UI
            self.root.after(0, self.refresh_all_data)
            
        except Exception as e:
            self.update_status(f"Error processing message: {str(e)}")
    
    def save_deadline_summary(self, title, deadline_str):
        """Save deadline to file"""
        try:
            deadline_obj = datetime.strptime(deadline_str, "%d/%m/%y %I:%M %p")
            data = {
                "title": title,
                "deadline": deadline_obj.strftime("%Y-%m-%d %H:%M")
            }
            
            try:
                with open(DEADLINE_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except:
                existing = []
            
            existing.append(data)
            
            with open(DEADLINE_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.update_status(f"Could not save deadline: {str(e)}")
    
    def save_event(self, title, deadline, links):
        """Save event/hackathon to file"""
        try:
            event_data = {
                "title": title,
                "date": deadline or "TBD",
                "links": links,
                "added": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            
            try:
                with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except:
                existing = []
            
            existing.append(event_data)
            
            with open(EVENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.update_status(f"Could not save event: {str(e)}")
    
    def update_status(self, message):
        """Update status label"""
        self.status_label.configure(text=f"Status: {message}")
        self.root.update_idletasks()
    
    # Utility functions from original code
    def extract_links(self, text):
        return re.findall(r'(https?://[^\s]+)', text)

    def classify_message(self, text):
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

    def extract_degree_branch_campus(self, text):
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

    def extract_deadline(self, text):
        match = re.search(r'(on or before|by)\s([0-9]{1,2}/[0-9]{1,2}/[0-9]{2})(\s*[0-9]{1,2}[:.][0-9]{2}\s*(am|pm)?)?', text.lower())
        if match:
            date_part = match.group(2)
            time_part = match.group(3).strip() if match.group(3) else "11:59 PM"
            return f"{date_part} {time_part}".strip()
        return None

    def get_summary(self, text):
        """Generate summary with GPU acceleration and caching"""
        try:
            if self.summarizer and len(text) > 100:
                # Clean and prepare text
                cleaned_text = re.sub(r'\s+', ' ', text.strip())
                
                # Use GPU-optimized settings
                result = self.summarizer(
                    cleaned_text, 
                    max_length=80, 
                    min_length=20, 
                    do_sample=False,
                    clean_up_tokenization_spaces=True
                )
                return result[0]['summary_text']
            else:
                # Fallback to truncation for short texts or when summarizer unavailable
                return text[:120] + "..." if len(text) > 120 else text
        except Exception as e:
            # Fallback on error
            return text[:120] + "..." if len(text) > 120 else text

# Main application
if __name__ == "__main__":
    root = tk.Tk()
    app = PlacementWidget(root)
    root.mainloop()