import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from datetime import datetime, timedelta
import threading
from telethon.sync import TelegramClient
from telethon import events  # Add this missing import
import re

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    'summary': os.path.join(BASE_DIR, "latest_summary.txt"),
    'deadlines': os.path.join(BASE_DIR, "deadlines.json"),
    'events': os.path.join(BASE_DIR, "events.json"),
    'applications': os.path.join(BASE_DIR, "applications.json")
}

# Telegram config - loaded from environment variables to avoid committing secrets
try:
    # optional .env support
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Required env vars: TELEGRAM_API_ID, TELEGRAM_API_HASH
# Optional: TELEGRAM_GROUP_NAME (defaults to 'Engineering 2026 batch')
try:
    API_ID = int(os.environ.get('TELEGRAM_API_ID') or os.environ.get('API_ID'))
    API_HASH = os.environ.get('TELEGRAM_API_HASH') or os.environ.get('API_HASH')
except Exception:
    API_ID = None
    API_HASH = None

GROUP_NAME = os.environ.get('TELEGRAM_GROUP_NAME', 'Engineering 2026 batch')
AUTO_REFRESH = 30 * 60 * 1000  # 30 mins

class PlacementTracker:
    def __init__(self, root):
        self.root = root
        self.telegram_running = False
        self.client = None
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        self.root.title("📢 Placement & Events Tracker")
        self.root.geometry("700x600")
        self.root.configure(bg="#f8f9fa")
        
        # Main container
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Header
        tk.Label(main, text="🎓 Placement & Events Dashboard", 
                font=("Helvetica", 16, "bold"), bg="#f8f9fa").pack(pady=(0, 10))
        
        # Controls
        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(0, 10))
        
        ttk.Button(controls, text="🔄 Refresh", command=self.refresh_all).pack(side="left", padx=5)
        self.tg_btn = ttk.Button(controls, text="🤖 Start Monitor", command=self.toggle_telegram)
        self.tg_btn.pack(side="left", padx=5)
        ttk.Button(controls, text="📜 Scan History", command=self.scan_history).pack(side="left", padx=5)
        
        # Status
        self.status = tk.Label(main, text="Ready", font=("Helvetica", 9), bg="#f8f9fa")
        self.status.pack(anchor="w")
        
        # Notebook
        self.nb = ttk.Notebook(main)
        self.nb.pack(fill="both", expand=True, pady=10)
        
        self.create_tabs()
        
    def create_tabs(self):
        # Updates Tab
        updates = ttk.Frame(self.nb)
        self.nb.add(updates, text="📋 Updates")
        
        # History scanner
        hist_frame = ttk.LabelFrame(updates, text="History Scanner", padding=5)
        hist_frame.pack(fill="x", padx=5, pady=5)
        
        hist_ctrl = ttk.Frame(hist_frame)
        hist_ctrl.pack(fill="x")
        
        tk.Label(hist_ctrl, text="Days:").pack(side="left")
        self.hist_days = tk.StringVar(value="7")
        ttk.Combobox(hist_ctrl, textvariable=self.hist_days, values=["1", "3", "7", "14", "30"], width=5).pack(side="left", padx=5)
        
        self.hist_progress = ttk.Progressbar(hist_ctrl, mode='indeterminate')
        self.hist_progress.pack(side="left", fill="x", expand=True, padx=10)
        
        self.hist_results = scrolledtext.ScrolledText(hist_frame, height=4, font=("Consolas", 9))
        self.hist_results.pack(fill="x", pady=5)
        
        # Summary
        tk.Label(updates, text="Latest Summary", font=("Helvetica", 11, "bold")).pack(pady=5, anchor="w")
        self.summary_text = scrolledtext.ScrolledText(updates, height=15, font=("Consolas", 9))
        self.summary_text.pack(fill="both", expand=True, padx=5)
        
        # Deadlines Tab
        deadlines = ttk.Frame(self.nb)
        self.nb.add(deadlines, text="📅 Deadlines")
        
        # Filter
        filter_frame = ttk.Frame(deadlines)
        filter_frame.pack(fill="x", padx=5, pady=5)
        
        self.deadline_filter = tk.StringVar(value="upcoming")
        for text, value in [("Upcoming", "upcoming"), ("This Week", "week"), ("All", "all")]:
            ttk.Radiobutton(filter_frame, text=text, variable=self.deadline_filter, 
                          value=value, command=self.filter_deadlines).pack(side="left", padx=5)
        
        self.deadlines_text = scrolledtext.ScrolledText(deadlines, height=20, font=("Consolas", 9))
        self.deadlines_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Events Tab
        events = ttk.Frame(self.nb)
        self.nb.add(events, text="🏆 Events")
        
        self.events_text = scrolledtext.ScrolledText(events, height=20, font=("Consolas", 9))
        self.events_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Applications Tab
        apps = ttk.Frame(self.nb)
        self.nb.add(apps, text="✅ Applications")
        
        # Add form
        add_frame = ttk.LabelFrame(apps, text="Add Application", padding=5)
        add_frame.pack(fill="x", padx=5, pady=5)
        
        # Entry grid
        entries = ttk.Frame(add_frame)
        entries.pack(fill="x")
        
        # Create entry fields
        self.entries = {}
        fields = [("Company", 0, 0), ("Position", 0, 2), ("Deadline", 1, 0)]
        for field, row, col in fields:
            tk.Label(entries, text=f"{field}:").grid(row=row, column=col, sticky="w", padx=5)
            self.entries[field.lower()] = ttk.Entry(entries, width=20)
            self.entries[field.lower()].grid(row=row, column=col+1, padx=5, pady=2)
        
        # Status dropdown
        tk.Label(entries, text="Status:").grid(row=1, column=2, sticky="w", padx=5)
        self.status_var = tk.StringVar(value="Not Applied")
        ttk.Combobox(entries, textvariable=self.status_var, 
                    values=["Not Applied", "Applied", "Test Scheduled", "Interview Scheduled", "Completed"]).grid(row=1, column=3, padx=5)
        
        ttk.Button(add_frame, text="➕ Add", command=self.add_application).pack(pady=10)
        
        # Applications list
        list_frame = ttk.LabelFrame(apps, text="Applications", padding=5)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Treeview
        cols = ("Company", "Position", "Deadline", "Status", "Added")
        self.app_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        
        for col in cols:
            self.app_tree.heading(col, text=col)
            self.app_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.app_tree.yview)
        self.app_tree.configure(yscrollcommand=scrollbar.set)
        self.app_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # App buttons
        btn_frame = ttk.Frame(apps)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="🗑️ Delete", command=self.delete_app).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="✏️ Edit Status", command=self.edit_app_status).pack(side="left", padx=5)
        
        # Context menu
        self.app_tree.bind("<Button-3>", self.show_context_menu)
    
    def load_data(self):
        """Load and refresh all data"""
        self.refresh_all()
        self.root.after(AUTO_REFRESH, self.load_data)
    
    def refresh_all(self):
        """Refresh all tabs"""
        self.update_status("Refreshing...")
        
        # Summary
        summary = self.read_file(FILES['summary'], "No summary available")
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, summary)
        
        # Other tabs
        self.filter_deadlines()
        self.refresh_events()
        self.refresh_applications()
        
        self.update_status("Refreshed")
    
    def read_file(self, filepath, default=""):
        """Read file with error handling"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return default
    
    def load_json(self, filepath):
        """Load JSON with error handling"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def save_json(self, filepath, data):
        """Save JSON with error handling"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")
    
    def filter_deadlines(self):
        """Filter and display deadlines"""
        data = self.load_json(FILES['deadlines'])
        now = datetime.now()
        week_later = now + timedelta(days=7)
        
        # Filter logic
        filter_type = self.deadline_filter.get()
        if filter_type == "upcoming":
            filtered = [d for d in data if self.parse_date(d.get('deadline', '')) > now]
        elif filter_type == "week":
            filtered = [d for d in data if now < self.parse_date(d.get('deadline', '')) <= week_later]
        else:
            filtered = data
        
        # Sort and display
        filtered.sort(key=lambda x: self.parse_date(x.get('deadline', '')))
        
        self.deadlines_text.delete(1.0, tk.END)
        if filtered:
            for item in filtered:
                deadline = self.parse_date(item.get('deadline', ''))
                time_left = deadline - now
                
                if time_left.days > 0:
                    time_str = f"({time_left.days} days)"
                elif time_left.total_seconds() > 0:
                    time_str = f"({int(time_left.total_seconds()//3600)} hours)"
                else:
                    time_str = "⚠️ EXPIRED"
                
                self.deadlines_text.insert(tk.END, f"📌 {item.get('title', 'Deadline')}\n")
                self.deadlines_text.insert(tk.END, f"🕒 {deadline.strftime('%d/%m/%Y %I:%M %p')} {time_str}\n\n")
        else:
            self.deadlines_text.insert(tk.END, f"No {filter_type} deadlines found.")
    
    def parse_date(self, date_str):
        """Parse date string safely"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except:
            return datetime.min
    
    def refresh_events(self):
        """Refresh events display"""
        events = self.load_json(FILES['events'])
        
        self.events_text.delete(1.0, tk.END)
        if events:
            for event in events:
                self.events_text.insert(tk.END, f"🏆 {event.get('title', 'Event')}\n")
                self.events_text.insert(tk.END, f"📅 {event.get('date', 'TBD')}\n")
                if event.get('description'):
                    self.events_text.insert(tk.END, f"📝 {event['description']}\n")
                if event.get('links'):
                    for link in event['links']:
                        self.events_text.insert(tk.END, f"🔗 {link}\n")
                self.events_text.insert(tk.END, "\n" + "-"*50 + "\n\n")
        else:
            self.events_text.insert(tk.END, "No events found.")
    
    def add_application(self):
        """Add new application"""
        company = self.entries['company'].get().strip()
        position = self.entries['position'].get().strip()
        deadline = self.entries['deadline'].get().strip()
        status = self.status_var.get()
        
        if not company or not position:
            messagebox.showerror("Error", "Company and Position required!")
            return
        
        apps = self.load_json(FILES['applications'])
        
        new_app = {
            "id": len(apps) + 1,
            "company": company,
            "position": position,
            "deadline": deadline,
            "status": status,
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        apps.append(new_app)
        self.save_json(FILES['applications'], apps)
        
        # Clear form
        for entry in self.entries.values():
            entry.delete(0, tk.END)
        self.status_var.set("Not Applied")
        
        self.refresh_applications()
        self.update_status(f"Added: {company} - {position}")
    
    def refresh_applications(self):
        """Refresh applications tree"""
        for item in self.app_tree.get_children():
            self.app_tree.delete(item)
        
        apps = self.load_json(FILES['applications'])
        apps.sort(key=lambda x: x.get('added_date', ''), reverse=True)
        
        for app in apps:
            self.app_tree.insert("", "end", values=(
                app.get('company', ''),
                app.get('position', ''),
                app.get('deadline', ''),
                app.get('status', ''),
                app.get('added_date', '').split()[0]
            ), tags=(app.get('id'),))
    
    def delete_app(self):
        """Delete selected application"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select an application first!")
            return
        
        if messagebox.askyesno("Confirm", "Delete this application?"):
            app_id = self.app_tree.item(selected[0], 'tags')[0]
            apps = self.load_json(FILES['applications'])
            apps = [app for app in apps if str(app.get('id')) != str(app_id)]
            self.save_json(FILES['applications'], apps)
            self.refresh_applications()
            self.update_status("Application deleted")
    
    def edit_app_status(self):
        """Edit application status"""
        selected = self.app_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select an application first!")
            return
        
        item = selected[0]
        current_status = self.app_tree.item(item, 'values')[3]
        app_id = self.app_tree.item(item, 'tags')[0]
        
        # Status dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Status")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Select status:").pack(pady=10)
        
        status_var = tk.StringVar(value=current_status)
        statuses = ["Not Applied", "Applied", "Test Scheduled", "Interview Scheduled", "Completed", "Rejected"]
        
        for status in statuses:
            ttk.Radiobutton(dialog, text=status, variable=status_var, value=status).pack(anchor="w", padx=20)
        
        def update():
            apps = self.load_json(FILES['applications'])
            for app in apps:
                if str(app.get('id')) == str(app_id):
                    app['status'] = status_var.get()
                    break
            self.save_json(FILES['applications'], apps)
            self.refresh_applications()
            self.update_status(f"Status updated: {status_var.get()}")
            dialog.destroy()
        
        ttk.Button(dialog, text="Update", command=update).pack(pady=20)
    
    def show_context_menu(self, event):
        """Show context menu for applications"""
        item = self.app_tree.identify_row(event.y)
        if item:
            self.app_tree.selection_set(item)
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Edit Status", command=self.edit_app_status)
            menu.add_command(label="Delete", command=self.delete_app)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
    
    def toggle_telegram(self):
        """Toggle Telegram monitoring"""
        if self.telegram_running:
            self.stop_telegram()
        else:
            self.start_telegram()
    
    def start_telegram(self):
        """Start Telegram monitoring"""
        self.telegram_running = True
        self.tg_btn.configure(text="⏹️ Stop Monitor")
        threading.Thread(target=self.telegram_worker, daemon=True).start()
        self.update_status("Telegram monitoring started")
    
    def stop_telegram(self):
        """Stop Telegram monitoring"""
        self.telegram_running = False
        self.tg_btn.configure(text="🤖 Start Monitor")
        if self.client:
            self.client.disconnect()
        self.update_status("Telegram monitoring stopped")
    
    def telegram_worker(self):
        """Telegram monitoring worker"""
        try:
            if not API_ID or not API_HASH:
                # Update status and return without attempting to connect
                self.root.after(0, lambda: self.update_status(
                    "Missing TELEGRAM_API_ID/TELEGRAM_API_HASH in environment. Telegram disabled."))
                return

            self.client = TelegramClient('session', API_ID, API_HASH)
            self.client.start()

            @self.client.on(events.NewMessage)
            async def handler(event):
                if event.is_group and GROUP_NAME.lower() in event.chat.title.lower():
                    await self.process_message(event.message)

            self.client.run_until_disconnected()
        except Exception as e:
            error_msg = f"Telegram error: {str(e)}"
            self.root.after(0, lambda: self.update_status(error_msg))
    
    async def process_message(self, message):
        """Process incoming Telegram message"""
        if not message.text or len(message.text.strip()) < 20:
            return
        
        text = message.text
        
        # Extract information
        category = self.classify_message(text)
        deadline = self.extract_deadline(text)
        summary = self.create_summary(text)
        
        # Save summary
        summary_entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {category}\n{summary}\n{'-'*50}\n\n"
        
        try:
            with open(FILES['summary'], 'a', encoding='utf-8') as f:
                f.write(summary_entry)
        except:
            pass
        
        # Save deadline if found
        if deadline:
            self.save_deadline(summary, deadline)
        
        # Update UI
        self.root.after(0, self.refresh_all)
    
    def classify_message(self, text):
        """Classify message type"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['hackathon', 'competition', 'contest']):
            return "🏆 EVENT"
        elif any(word in text_lower for word in ['deadline', 'last date', 'apply']):
            return "📅 DEADLINE"
        elif any(word in text_lower for word in ['placement', 'recruitment', 'hiring', 'job']):
            return "💼 PLACEMENT"
        else:
            return "📢 UPDATE"
    
    def extract_deadline(self, text):
        """Extract deadline from text"""
        # Simple date patterns
        patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                try:
                    date_str = match.group(1)
                    # Try different parsing formats
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%d %B %Y']:
                        try:
                            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d %H:%M")
                        except:
                            continue
                except:
                    pass
        return None
    
    def create_summary(self, text):
        """Create summary of text"""
        # Simple summarization - just take first few sentences
        sentences = text.split('.')
        summary = '. '.join(sentences[:2])
        return summary[:200] + ('...' if len(summary) > 200 else '')
    
    def save_deadline(self, title, deadline):
        """Save deadline to file"""
        deadlines = self.load_json(FILES['deadlines'])
        
        new_deadline = {
            "title": title[:100],
            "deadline": deadline,
            "added": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        deadlines.append(new_deadline)
        self.save_json(FILES['deadlines'], deadlines)
    
    def scan_history(self):
        """Scan message history"""
        if self.telegram_running:
            messagebox.showwarning("Warning", "Stop monitoring first!")
            return
        
        try:
            days = int(self.hist_days.get())
        except:
            days = 7
        
        if not messagebox.askyesno("Confirm", f"Scan last {days} days?"):
            return
        
        self.hist_results.delete(1.0, tk.END)
        self.hist_results.insert(tk.END, "Starting scan...\n")
        self.hist_progress.start()
        
        threading.Thread(target=self.history_scan_worker, args=(days,), daemon=True).start()
    
    def history_scan_worker(self, days):
        """History scan worker"""
        try:
            with TelegramClient('history_session', API_ID, API_HASH) as client:
                # Find group
                group = None
                for dialog in client.iter_dialogs():
                    if dialog.is_group and GROUP_NAME.lower() in dialog.name.lower():
                        group = dialog.entity
                        break
                
                if not group:
                    self.root.after(0, lambda: self.scan_complete("Group not found!"))
                    return
                
                # Scan messages
                start_date = datetime.now() - timedelta(days=days)
                keywords = ['placement', 'recruitment', 'hackathon', 'deadline', 'apply']
                
                found_messages = []
                count = 0
                
                for message in client.iter_messages(group, offset_date=start_date, limit=500):
                    if message.date < start_date:
                        break
                    
                    if message.text and any(kw in message.text.lower() for kw in keywords):
                        found_messages.append({
                            'text': message.text,
                            'date': message.date.strftime("%Y-%m-%d %H:%M")
                        })
                        count += 1
                        
                        if count % 10 == 0:
                            # Fix: Capture the value immediately
                            progress_msg = f"Found {count} messages..."
                            self.root.after(0, lambda msg=progress_msg: self.update_scan_progress(msg))
                
                self.root.after(0, lambda: self.process_scan_results(found_messages))
                            
        except Exception as e:
            # Fix: Capture the error message immediately
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.scan_complete(error_msg))
    
    def update_scan_progress(self, msg):
        """Update scan progress"""
        self.hist_results.insert(tk.END, f"{msg}\n")
        self.hist_results.see(tk.END)
    
    def process_scan_results(self, messages):
        """Process scan results"""
        new_items = 0
        
        for msg in messages:
            category = self.classify_message(msg['text'])
            deadline = self.extract_deadline(msg['text'])
            summary = self.create_summary(msg['text'])
            
            if deadline:
                self.save_deadline(summary, deadline)
                new_items += 1
        
        self.scan_complete(f"Scan complete! Found {len(messages)} messages, added {new_items} items.")
        self.refresh_all()
    
    def scan_complete(self, message):
        """Complete history scan"""
        self.hist_progress.stop()
        self.hist_results.insert(tk.END, f"\n{message}\n")
        self.hist_results.see(tk.END)
    
    def update_status(self, message):
        """Update status label"""
        self.status.configure(text=f"Status: {message}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PlacementTracker(root)
    root.mainloop()
# added a comment