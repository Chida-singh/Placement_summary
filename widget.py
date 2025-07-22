import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from datetime import datetime, timedelta
import threading
import re
import asyncio
from telethon.sync import TelegramClient
from telethon import events

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES = {
    'summary': os.path.join(BASE_DIR, "latest_summary.txt"),
    'deadlines': os.path.join(BASE_DIR, "deadlines.json"),
    'events': os.path.join(BASE_DIR, "events.json"),
    'applications': os.path.join(BASE_DIR, "applications.json")
}

# Telegram config
API_ID = 20581631
API_HASH = 'e048725183f82fe4e8e4e826549edc88'
GROUP_NAME = 'Engineering 2026 batch'
AUTO_REFRESH = 30 * 60 * 1000  # 30 mins

class PlacementTracker:
    def __init__(self, root):
        self.root = root
        self.telegram_running = False
        self.client = None
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        self.root.title("Placement Tracker")
        self.root.geometry("800x600")
        
        # Main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Summary Tab
        self.summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.summary_frame, text="Summary")
        
        self.summary_text = scrolledtext.ScrolledText(self.summary_frame, height=15)
        self.summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        summary_btn_frame = ttk.Frame(self.summary_frame)
        summary_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(summary_btn_frame, text="Refresh", command=self.refresh_summary).pack(side=tk.LEFT, padx=2)
        ttk.Button(summary_btn_frame, text="Clear", command=self.clear_summary).pack(side=tk.LEFT, padx=2)

        # Deadlines Tab
        self.deadlines_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.deadlines_frame, text="Deadlines")
        
        self.deadlines_tree = ttk.Treeview(self.deadlines_frame, columns=("deadline", "added"), show="tree headings")
        self.deadlines_tree.heading("#0", text="Title")
        self.deadlines_tree.heading("deadline", text="Deadline")
        self.deadlines_tree.heading("added", text="Added")
        self.deadlines_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        deadline_btn_frame = ttk.Frame(self.deadlines_frame)
        deadline_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(deadline_btn_frame, text="Add Manual", command=self.add_manual_deadline).pack(side=tk.LEFT, padx=2)
        ttk.Button(deadline_btn_frame, text="Delete", command=self.delete_deadline).pack(side=tk.LEFT, padx=2)
        ttk.Button(deadline_btn_frame, text="Refresh", command=self.refresh_deadlines).pack(side=tk.LEFT, padx=2)

        # History Scan Tab
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="History Scan")
        
        hist_control_frame = ttk.Frame(self.history_frame)
        hist_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(hist_control_frame, text="Days to scan:").pack(side=tk.LEFT)
        self.hist_days = tk.StringVar(value="7")
        ttk.Entry(hist_control_frame, textvariable=self.hist_days, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(hist_control_frame, text="Start Scan", command=self.scan_history).pack(side=tk.LEFT, padx=5)
        
        self.hist_progress = ttk.Progressbar(hist_control_frame, mode='indeterminate')
        self.hist_progress.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.hist_results = scrolledtext.ScrolledText(self.history_frame, height=20)
        self.hist_results.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Monitoring Tab
        self.monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.monitor_frame, text="Live Monitor")
        
        monitor_btn_frame = ttk.Frame(self.monitor_frame)
        monitor_btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.monitor_btn = ttk.Button(monitor_btn_frame, text="Start Monitoring", command=self.toggle_monitoring)
        self.monitor_btn.pack(side=tk.LEFT, padx=2)
        
        self.status_label = ttk.Label(monitor_btn_frame, text="Status: Stopped")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.monitor_text = scrolledtext.ScrolledText(self.monitor_frame, height=20)
        self.monitor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def load_data(self):
        self.refresh_all()

    def load_json(self, filepath):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return []

    def save_json(self, filepath, data):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save {filepath}: {e}")

    def refresh_all(self):
        self.refresh_summary()
        self.refresh_deadlines()

    def refresh_summary(self):
        self.summary_text.delete(1.0, tk.END)
        
        # Load deadlines
        deadlines = self.load_json(FILES['deadlines'])
        upcoming = [d for d in deadlines if datetime.strptime(d['deadline'], '%Y-%m-%d %H:%M') > datetime.now()]
        upcoming.sort(key=lambda x: x['deadline'])
        
        summary = f"=== PLACEMENT TRACKER SUMMARY ===\n"
        summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        summary += f"📅 UPCOMING DEADLINES ({len(upcoming)}):\n"
        
        for deadline in upcoming[:10]:  # Show top 10
            dt = datetime.strptime(deadline['deadline'], '%Y-%m-%d %H:%M')
            days_left = (dt - datetime.now()).days
            summary += f"• {deadline['title'][:50]}...\n"
            summary += f"  Deadline: {dt.strftime('%d %b %Y')} ({days_left} days left)\n\n"
        
        if not upcoming:
            summary += "No upcoming deadlines found.\n\n"
        
        summary += "💡 TIP: Use History Scan to find missed opportunities!\n"
        
        self.summary_text.insert(tk.END, summary)

    def clear_summary(self):
        self.summary_text.delete(1.0, tk.END)

    def refresh_deadlines(self):
        for item in self.deadlines_tree.get_children():
            self.deadlines_tree.delete(item)
        
        deadlines = self.load_json(FILES['deadlines'])
        for i, deadline in enumerate(deadlines):
            self.deadlines_tree.insert("", "end", values=(deadline['deadline'], deadline.get('added', 'N/A')), 
                                     text=deadline['title'])

    def add_manual_deadline(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Deadline")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Title:").pack(pady=5)
        title_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=title_var, width=50).pack(pady=5)
        
        ttk.Label(dialog, text="Deadline (YYYY-MM-DD HH:MM):").pack(pady=5)
        deadline_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d 23:59"))
        ttk.Entry(dialog, textvariable=deadline_var, width=30).pack(pady=5)
        
        def save_deadline():
            try:
                title = title_var.get().strip()
                deadline_str = deadline_var.get().strip()
                
                if not title:
                    messagebox.showerror("Error", "Title is required")
                    return
                
                # Validate deadline format
                datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
                
                self.save_deadline(title, deadline_str)
                self.refresh_deadlines()
                dialog.destroy()
                
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD HH:MM")
        
        ttk.Button(dialog, text="Save", command=save_deadline).pack(pady=10)

    def delete_deadline(self):
        selected = self.deadlines_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a deadline to delete")
            return
        
        if messagebox.askyesno("Confirm", "Delete selected deadline?"):
            deadlines = self.load_json(FILES['deadlines'])
            item = self.deadlines_tree.item(selected[0])
            title_to_delete = item['text']
            
            deadlines = [d for d in deadlines if d['title'] != title_to_delete]
            self.save_json(FILES['deadlines'], deadlines)
            self.refresh_deadlines()

    def toggle_monitoring(self):
        if self.telegram_running:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def start_monitoring(self):
        self.telegram_running = True
        self.monitor_btn.config(text="Stop Monitoring")
        self.status_label.config(text="Status: Starting...")
        self.monitor_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Starting monitoring...\n")
        
        threading.Thread(target=self.monitor_worker, daemon=True).start()

    def stop_monitoring(self):
        self.telegram_running = False
        self.monitor_btn.config(text="Start Monitoring")
        self.status_label.config(text="Status: Stopped")
        self.monitor_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring stopped.\n")

    def monitor_worker(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.monitor_telegram())
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"Monitoring error: {e}"))
            self.root.after(0, self.stop_monitoring)

    async def monitor_telegram(self):
        try:
            async with TelegramClient('monitor_session', API_ID, API_HASH) as client:
                self.client = client
                self.root.after(0, lambda: self.status_label.config(text="Status: Connected"))
                self.root.after(0, lambda: self.log_message("Connected to Telegram"))
                
                # Find group
                group = None
                async for dialog in client.iter_dialogs():
                    if dialog.is_group and GROUP_NAME.lower() in dialog.name.lower():
                        group = dialog.entity
                        break
                
                if not group:
                    self.root.after(0, lambda: self.log_message(f"Group '{GROUP_NAME}' not found"))
                    return
                
                self.root.after(0, lambda: self.log_message(f"Monitoring group: {GROUP_NAME}"))
                
                @client.on(events.NewMessage(chats=group))
                async def handler(event):
                    if event.text:
                        self.root.after(0, lambda: self.process_new_message(event.text))
                
                # Keep running
                while self.telegram_running:
                    await asyncio.sleep(1)
                    
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"Connection error: {e}"))

    def process_new_message(self, text):
        keywords = ['placement', 'recruitment', 'hackathon', 'deadline', 'apply', 'hiring', 'internship']
        
        if any(kw in text.lower() for kw in keywords):
            timestamp = datetime.now().strftime('%H:%M:%S')
            category = self.classify_message(text)
            
            self.log_message(f"🔔 {category} detected!")
            self.log_message(f"Preview: {text[:100]}...")
            
            # Try to extract deadline
            deadline = self.extract_deadline(text)
            if deadline:
                summary = self.create_summary(text)
                self.save_deadline(summary, deadline)
                self.log_message(f"💾 Auto-saved deadline: {deadline}")
                self.root.after(0, self.refresh_deadlines)

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.monitor_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.monitor_text.see(tk.END)

    def scan_history(self):
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
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.scan_history_async(days))
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, lambda: self.scan_complete(error_msg))

    async def scan_history_async(self, days):
        async with TelegramClient('history_session', API_ID, API_HASH) as client:
            # Debug: List all available groups
            self.root.after(0, lambda: self.update_scan_progress("Listing available groups..."))
            group_list = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    group_list.append(dialog.name)
                    self.root.after(0, lambda name=dialog.name: self.update_scan_progress(f"Found group: {name}"))

            # Find target group
            group = None
            async for dialog in client.iter_dialogs():
                if dialog.is_group and GROUP_NAME.lower() in dialog.name.lower():
                    group = dialog.entity
                    self.root.after(0, lambda: self.update_scan_progress(f"Selected group: {dialog.name}"))
                    break

            if not group:
                available_groups = "\n".join(group_list[:10])  # Show first 10 groups
                self.root.after(0, lambda: self.scan_complete(f"Group '{GROUP_NAME}' not found!\n\nAvailable groups:\n{available_groups}"))
                return

            # Fix timezone issue - make start_date timezone-aware
            from datetime import timezone
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            keywords = ['placement', 'recruitment', 'hackathon', 'deadline', 'apply', 'job', 'hiring', 'internship', 'opportunity']

            self.root.after(0, lambda: self.update_scan_progress(f"Scanning messages from {start_date.strftime('%Y-%m-%d')}..."))

            found_messages = []
            total_messages = 0
            keyword_matches = 0

            async for message in client.iter_messages(group, offset_date=start_date, limit=500):
                total_messages += 1
                
                # Convert message.date to naive datetime for comparison if needed
                msg_date = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date
                start_date_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
                
                if msg_date < start_date_naive:
                    break

                # Debug: Show every 50th message
                if total_messages % 50 == 0:
                    self.root.after(0, lambda count=total_messages: self.update_scan_progress(f"Processed {count} messages..."))

                # Debug: Show ALL messages in small groups for debugging
                if total_messages <= 10:
                    if message.text:
                        preview = message.text[:150].replace('\n', ' ')
                        msg_date_str = message.date.strftime('%Y-%m-%d %H:%M')
                        self.root.after(0, lambda prev=preview, date=msg_date_str: 
                                      self.update_scan_progress(f"[{date}] Message: '{prev}...'"))
                    else:
                        msg_date_str = message.date.strftime('%Y-%m-%d %H:%M')
                        self.root.after(0, lambda date=msg_date_str: 
                                      self.update_scan_progress(f"[{date}] Non-text message (photo/file/etc)"))

                if message.text:
                    # Check for keywords
                    text_lower = message.text.lower()
                    matching_keywords = [kw for kw in keywords if kw in text_lower]
                    
                    if matching_keywords:
                        keyword_matches += 1
                        found_messages.append({
                            'text': message.text,
                            'date': message.date.strftime("%Y-%m-%d %H:%M"),
                            'keywords': matching_keywords
                        })
                        
                        # Show first few matches for debugging
                        if keyword_matches <= 3:
                            preview = message.text[:100].replace('\n', ' ')
                            self.root.after(0, lambda prev=preview, kw=matching_keywords: 
                                          self.update_scan_progress(f"Match found: {kw} in '{prev}...'"))

            self.root.after(0, lambda: self.update_scan_progress(f"Scan finished. Total messages: {total_messages}, Keyword matches: {keyword_matches}"))
            self.root.after(0, lambda: self.process_scan_results(found_messages))

    def update_scan_progress(self, msg):
        self.hist_results.insert(tk.END, f"{msg}\n")
        self.hist_results.see(tk.END)

    def process_scan_results(self, messages):
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
        self.hist_progress.stop()
        self.hist_results.insert(tk.END, f"\n{message}\n")
        self.hist_results.see(tk.END)

    def classify_message(self, text):
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
        patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{2,4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                date_str = match.group(1)
                for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%d %B %Y']:
                    try:
                        return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d %H:%M")
                    except:
                        continue
        return None

    def create_summary(self, text):
        sentences = text.split('.')
        summary = '. '.join(sentences[:2])
        return summary[:200] + ('...' if len(summary) > 200 else '')

    def save_deadline(self, title, deadline):
        deadlines = self.load_json(FILES['deadlines'])
        # Check for duplicates
        if not any(d['title'] == title and d['deadline'] == deadline for d in deadlines):
            new_deadline = {
                "title": title[:100],
                "deadline": deadline,
                "added": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            deadlines.append(new_deadline)
            self.save_json(FILES['deadlines'], deadlines)

# Launcher
if __name__ == "__main__":
    root = tk.Tk()
    app = PlacementTracker(root)
    root.mainloop()
