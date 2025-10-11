#!/usr/bin/env python3
"""
PARALLEL REINDEXING MASTER SCRIPT
Runs all specialized reindexing scripts in parallel for maximum speed
"""

import os
import subprocess
import sys
import time
import threading
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class ScriptRunner:
    def __init__(self, script_name, description):
        self.script_name = script_name
        self.description = description
        self.process = None
        self.start_time = None
        self.end_time = None
        self.return_code = None
        self.output = []
        
    def run(self):
        """Run the script in a subprocess."""
        print(f"🚀 Starting {self.description}...")
        self.start_time = time.time()
        
        script_path = os.path.join(os.path.dirname(__file__), self.script_name)
        python_path = sys.executable
        
        try:
            self.process = subprocess.Popen(
                [python_path, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Read output in real-time
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output.append(line.strip())
                    print(f"[{self.description}] {line.strip()}")
            
            self.process.wait()
            self.return_code = self.process.returncode
            self.end_time = time.time()
            
        except Exception as e:
            print(f"❌ Error running {self.description}: {e}")
            self.return_code = -1
            self.end_time = time.time()
    
    def get_duration(self):
        """Get the duration in minutes."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) / 60
        return 0
    
    def is_success(self):
        """Check if the script completed successfully."""
        return self.return_code == 0

def run_parallel_reindexing():
    """Run all reindexing scripts in parallel."""
    print("🔥 PARALLEL REINDEXING - MAXIMUM SPEED MODE")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Define all scripts to run
    scripts = [
        ScriptRunner("reindex_pdfs.py", "PDF Files"),
        ScriptRunner("reindex_word.py", "Word Documents"),
        ScriptRunner("reindex_emails.py", "Email Files"),
        ScriptRunner("reindex_text.py", "Text Files"),
    ]
    
    # Start all scripts in parallel using threads
    threads = []
    overall_start = time.time()
    
    for script in scripts:
        thread = threading.Thread(target=script.run)
        thread.daemon = True
        thread.start()
        threads.append(thread)
        time.sleep(1)  # Small delay between starts
    
    print(f"🏃 All {len(scripts)} scripts started in parallel!")
    print("⏳ Waiting for completion...")
    print()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    overall_end = time.time()
    total_duration = (overall_end - overall_start) / 60
    
    # Print final summary
    print()
    print("🎉 PARALLEL REINDEXING COMPLETE!")
    print("=" * 80)
    print(f"Total time: {total_duration:.1f} minutes")
    print()
    
    success_count = 0
    failed_count = 0
    
    for script in scripts:
        status = "✅ SUCCESS" if script.is_success() else "❌ FAILED"
        duration = script.get_duration()
        
        print(f"{status} {script.description}: {duration:.1f} minutes (exit code: {script.return_code})")
        
        if script.is_success():
            success_count += 1
        else:
            failed_count += 1
    
    print()
    print(f"📊 Summary: {success_count} successful, {failed_count} failed")
    
    if success_count == len(scripts):
        print("🎊 ALL SCRIPTS COMPLETED SUCCESSFULLY!")
        print("🤖 Your bot should now have fully updated content!")
    elif success_count > 0:
        print("⚠️  Some scripts completed successfully, others had issues.")
        print("📖 Check the output above for details on failed scripts.")
    else:
        print("💥 All scripts failed! Check your configuration and try again.")
    
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def check_requirements():
    """Check if all required environment variables are set."""
    required_vars = [
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_SEARCH_SERVICE_ENDPOINT", 
        "AZURE_SEARCH_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("Make sure your .env file is properly configured.")
        return False
    
    return True

def show_usage():
    """Show usage information."""
    print("🚀 PARALLEL REINDEXING SYSTEM")
    print("=" * 50)
    print()
    print("This system runs multiple specialized reindexing scripts in parallel:")
    print("• 📄 PDF files (.pdf)")
    print("• 📝 Word documents (.docx, .doc)")
    print("• 📧 Email files (.msg, .eml)")
    print("• 📄 Text files (.txt, .csv, .json, etc.)")
    print()
    print("Benefits:")
    print("✅ Much faster than sequential processing")
    print("✅ Each script optimized for its file type")
    print("✅ Real-time progress monitoring")
    print("✅ Only processes files that need updating")
    print()
    print("Usage:")
    print("  python run_parallel_reindex.py")
    print()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
        sys.exit(0)
    
    print("🔍 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    print("✅ Requirements check passed!")
    print()
    
    try:
        run_parallel_reindexing()
    except KeyboardInterrupt:
        print("\\n⏹️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\\n💥 Unexpected error: {e}")
        sys.exit(1)
