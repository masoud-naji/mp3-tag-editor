import tkinter as tk
from tkinter import ttk, filedialog, font
import pandas as pd
import os
import sys
import eyed3
import threading
import queue


# Function to load MP3 tags into a DataFrame
def load_mp3_tags(directory, progress_queue):
    data = []
    files = [f for f in os.listdir(directory) if f.lower().endswith('.mp3')]
    total_files = len(files)

    for i, file in enumerate(files):
        try:
            progress_queue.put((i + 1, total_files))  # Update progress using queue
            file_path = os.path.join(directory, file)
            audiofile = eyed3.load(file_path)
            if audiofile and audiofile.tag:
                data.append({
                    "Filename": file,
                    "Title": audiofile.tag.title if audiofile.tag.title else "",
                    "Artist": audiofile.tag.artist if audiofile.tag.artist else "",
                    "Album": audiofile.tag.album if audiofile.tag.album else "",
                    "Lyrics": audiofile.tag.lyrics[0].text if audiofile.tag.lyrics else ""
                })
        except Exception as e:
            print(f"Error processing file {file}: {e}")

    progress_queue.put((total_files, total_files))  # Complete the progress
    return pd.DataFrame(data)

# Function to save MP3 tags from DataFrame back to files
def save_mp3_tags(dataframe, directory):
    for index, row in dataframe.iterrows():
        file_path = os.path.join(directory, row['Filename'])
        cleaned_lyrics = row['Lyrics'].strip()  # Strip whitespace and non-visible characters

        print(f"Processing {file_path} with lyrics: '{cleaned_lyrics}'")

        try:
            audiofile = eyed3.load(file_path)
            if audiofile and audiofile.tag:
                # Update basic tags
                audiofile.tag.title = row['Title']
                audiofile.tag.artist = row['Artist']
                audiofile.tag.album = row['Album']

                # Explicitly handle empty lyrics
                if cleaned_lyrics:
                    audiofile.tag.lyrics.set(cleaned_lyrics, 'eng')
                else:
                    # Use a placeholder for empty lyrics
                    audiofile.tag.lyrics.set('', 'eng')

                # Save the changes
                audiofile.tag.save(version=eyed3.id3.ID3_V2_3)
        except Exception as e:
            print(f"Error saving tags for {file_path}: {e}")

        print("Saving process completed.")

# Function to clean non-printable characters from DataFrame columns
def clean_non_printable_characters(dataframe):
    for col in dataframe.columns:
        if dataframe[col].dtype == object:
            dataframe[col] = dataframe[col].apply(lambda x: ''.join(filter(lambda c: c.isprintable(), str(x))))
    return dataframe

# Main GUI Application
class Mp3TagEditorApp:
    def __init__(self, root):
        self.root = root
        root.title("MP3 Tag Editor")

        # Define the dark theme colors
        dark_gray = '#2e2e2e'
        light_gray = '#555555'
        white = '#ffffff'
        hover_color = '#000000'

        # Set the initial window size and background color to dark gray
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = int(screen_width * 0.75)
        window_height = int(screen_height * 0.75)
        root.geometry(f"{window_width}x{window_height}")
        root.configure(bg=dark_gray)

        # Initialize the queue for progress updates and entry rows
        self.progress_queue = queue.Queue()
        self.entry_rows = []

        # Set up the style for ttk widgets to match the dark theme
        style = ttk.Style()
        style.theme_use('default')

        # Configure the style for ttk widgets
        style.configure('TButton', background=light_gray, foreground=white)
        style.configure('TFrame', background=dark_gray)
        style.configure('TLabel', background=dark_gray, foreground=white)
        style.configure('TEntry', background=light_gray, foreground=white)
        style.map('TButton',
                  background=[('active', light_gray)],
                  foreground=[('active', hover_color)])

        # Configure the Treeview for a dark theme
        style.configure("Treeview",
                        background=dark_gray,
                        foreground=white,
                        fieldbackground=dark_gray)
        style.map('Treeview',
                  background=[('selected', light_gray)])
        style.configure("Treeview.Heading",
                        background=light_gray,
                        foreground=white,
                        font=('Helvetica', 10, 'bold'))

        # Configure the Scrollbar for a dark theme
        style.configure("Vertical.TScrollbar", background=light_gray, troughcolor=dark_gray)

        # Progressbar style
        style.configure("green.Horizontal.TProgressbar", background=light_gray)

        # Apply the theme to the button frame and buttons
        self.button_frame = ttk.Frame(root, style='TFrame')
        self.button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.load_button = ttk.Button(self.button_frame, text="Load MP3 Tags", style='TButton', command=self.start_loading_tags)
        self.load_button.pack(side=tk.LEFT, padx=5)

        self.save_button = ttk.Button(self.button_frame, text="Save MP3 Tags", style='TButton', command=self.save_tags)
        self.save_button.pack(side=tk.LEFT, padx=5)

        self.message_label = ttk.Label(self.button_frame, text="", background=dark_gray, foreground=white)
        self.message_label.pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self.button_frame, style="green.Horizontal.TProgressbar", orient="horizontal", length=100, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.progress_label = ttk.Label(self.button_frame, text="0%", background=dark_gray, foreground=white)
        self.progress_label.pack(side=tk.LEFT, padx=5)

        self.entry_frame = ttk.Frame(root, style='TFrame')
        self.entry_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(self.entry_frame, bg=dark_gray, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.entry_frame, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        self.scrollable_frame = ttk.Frame(self.canvas, style='TFrame')

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Custom font for the widgets to control height
        self.custom_font = font.Font(size=10, family='Helvetica')

        # Define columns
        self.columns = ['Filename', 'Title', 'Artist', 'Album', 'Lyrics']

        # Store sort buttons by column name
        self.sort_buttons = {}
        for index, col in enumerate(self.columns):
            sort_button = ttk.Button(self.scrollable_frame, text=col, style='TButton', command=lambda c=col: self.sort_data(c))
            sort_button.grid(row=0, column=index, sticky='nsew', padx=5, pady=5)
            self.scrollable_frame.columnconfigure(index, weight=1)
            sort_button.current_sort_state = 'not_sorted'
            self.sort_buttons[col] = sort_button

        # Initialize a list to store edited data
        self.edited_data = []

        # Start the progress update loop
        self.update_progress()

    def start_loading_tags(self):
        self.directory = filedialog.askdirectory()
        if self.directory:
            threading.Thread(target=self.load_tags, daemon=True).start()

    def load_tags(self):
        self.dataframe = load_mp3_tags(self.directory, self.progress_queue)
        self.dataframe = clean_non_printable_characters(self.dataframe)  # Clean the data
        self.root.after(0, self.display_entries, self.dataframe)

    def display_entries(self, dataframe):
        # Clear existing widgets
        for row_entries in self.entry_rows:
            for entry in row_entries:
                entry.destroy()
        self.entry_rows.clear()

        # Set column weights for distribution
        for col_index, col_name in enumerate(self.columns):
            weight = 4 if col_name == 'Lyrics' else 1  # Corresponding to 40% and 15% distribution
            self.scrollable_frame.columnconfigure(col_index, weight=weight)

        # Re-create widgets with sorted data
        for index, row in dataframe.iterrows():
            row_entries = []
            for col_index, col in enumerate(self.columns):
                entry = tk.Entry(self.scrollable_frame, font=self.custom_font)
                entry.insert(0, row[col])
                entry.grid(row=index + 1, column=col_index, sticky='nsew')
                row_entries.append(entry)
            self.entry_rows.append(row_entries)

        # This function will be called whenever the root window is resized
        def on_root_resize(event):
            # Respond to the root's width change: adjust Entry widths proportionally
            window_width = self.root.winfo_width()
            total_weight = 4 + 1 * 4  # One 'Lyrics' column weight and four other columns
            lyrics_width = int(window_width * 4 / total_weight)
            other_width = int(window_width * 1 / total_weight)
            
            # Adjust the width of each entry widget
            for row_entries in self.entry_rows:
                for entry, col_name in zip(row_entries, self.columns):
                    new_width = lyrics_width if col_name == 'Lyrics' else other_width
                    entry.config(width=new_width // 8)  # Convert pixel width to character width approximation

        self.root.bind('<Configure>', on_root_resize)

        # Update the window to reflect changes
        self.root.update_idletasks()


    def update_progress(self):
            try:
                current, total = self.progress_queue.get_nowait()
                progress_percent = int((current / total) * 100)
                self.progress['value'] = progress_percent
                self.progress_label.config(text=f"{progress_percent}% ({current}/{total})")
                if progress_percent >= 100:
                    self.progress.config(style="green.Horizontal.TProgressbar")
            except queue.Empty:
                pass
            finally:
                # Schedule the next update
                self.root.after(100, self.update_progress)

    def on_lyrics_edit(self, event):
        edited_row_index = event.widget.grid_info()['row'] - 1
        column_index = event.widget.grid_info()['column']
        new_value = event.widget.get()
        self.dataframe.iloc[edited_row_index, column_index] = new_value  # Update the DataFrame

    def save_tags(self):
        if not self.directory:
            self.message_label.config(text="Error: No directory selected")
            return

        # Create a list to store the edited data
        edited_data = []
        for row_entries in self.entry_rows:
            edited_row = {col: row_entries[col_index].get() for col_index, col in enumerate(self.columns)}
            edited_data.append(edited_row)

        # Convert the edited data to a DataFrame
        edited_dataframe = pd.DataFrame(edited_data)

        # Start a new thread to save the tags
        threading.Thread(target=self.threaded_save_tags, args=(edited_dataframe,), daemon=True).start()

    def threaded_save_tags(self, dataframe):
        total = len(dataframe)
        for index, _ in enumerate(dataframe.iterrows()):
            save_mp3_tags(dataframe.iloc[[index]], self.directory)
            progress_percent = int(((index + 1) / total) * 100)
            self.progress['value'] = progress_percent
            self.progress_label.config(text=f"Saving {index + 1}/{total}...")
        
        self.progress_label.config(text="Tags saved successfully")
        # Hide the message after a delay
        self.root.after(5000, lambda: self.progress_label.config(text=""))

    def sort_data(self, column):
        if not self.directory:
            self.message_label.config(text="Error: No directory selected")
            return

        # Determine the new sorting state based on the current state
        sort_button = self.sort_buttons[column]
        new_sort_state = 'sorted_asc' if sort_button.current_sort_state == 'not_sorted' else 'sorted_desc' if sort_button.current_sort_state == 'sorted_asc' else 'not_sorted'
        
        # Update the sort button's appearance and sort the data
        sort_button.current_sort_state = new_sort_state
        sort_button.config(text=f"{column} {'⇧' if new_sort_state == 'sorted_asc' else '⇩' if new_sort_state == 'sorted_desc' else ''}")
        
        if new_sort_state != 'not_sorted':
            # Sort the DataFrame and reset the index
            self.dataframe = self.dataframe.sort_values(by=column, ascending=(new_sort_state == 'sorted_asc')).reset_index(drop=True)
            self.display_entries(self.dataframe)  # Update the display with the sorted DataFrame
        else:
            # If not sorted, reload the tags
            self.dataframe = load_mp3_tags(self.directory, self.progress_queue)
            self.display_entries(self.dataframe)  # Update the display with the reloaded DataFrame


if __name__ == "__main__":
    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(sys.argv[0]))

    root = tk.Tk()
    app = Mp3TagEditorApp(root)
    root.mainloop()
