import os
import json
import subprocess
import psutil


class LocalServerProcess:
    def __init__(self) -> None:
        self.metadata_dir = "spawn"
        os.makedirs(self.metadata_dir, exist_ok=True)
        self.metadata_path = f"{self.metadata_dir}/metadata.json"
        self.metadata = None
        self.start_server_command = ".venv/Scripts/python src/main.py"

    def get_metadata(self) -> dict:
        if self.metadata is None:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, "r") as jin:
                    self.metadata = json.load(jin)
            else:
                # Probably does not exist yet, so create one with an empty process id
                return {"pid": None}
            return self.metadata
        return self.metadata

    def set_metadata(self, data: dict) -> None:
        self.metadata = data
        with open(self.metadata_path, "w") as jout:
            json.dump(data, jout, indent=2)

    def spawn(self) -> None:
        metadata = self.get_metadata()

        # Step 1: Kill existing process if it exists
        old_pid = metadata.get("pid")
        if old_pid is not None:
            try:
                p = psutil.Process(old_pid)
                p.kill()  # or p.terminate() for a graceful shutdown
                print(f"Killed process with PID {old_pid}")
            except psutil.NoSuchProcess:
                print(f"No process with PID {old_pid} found.")
            except psutil.AccessDenied:
                print(f"Permission denied to kill PID {old_pid}.")

        # Step 2: Spawn new process
        process = subprocess.Popen(self.start_server_command.split())
        new_pid = process.pid
        print(f"Spawned new process with PID {new_pid}")

        # Step 3: Save new PID to metadata
        self.set_metadata({"pid": new_pid})


def main():
    LocalServerProcess().spawn()


if __name__ == "__main__":
    main()
