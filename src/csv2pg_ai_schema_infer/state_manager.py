"""State management for import operations."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

from .types import ImportPhase, ImportState, ImportStatus
from .utils.logger import logger
from .utils.validation import compute_file_checksum


class StateManager:
    """Manages import state persistence and recovery."""

    def __init__(self, state_file: Path):
        """
        Initialize state manager.

        Args:
            state_file: Path to state JSON file
        """
        self.state_file = state_file

    def save_state(self, state: ImportState) -> None:
        """
        Atomically save state to JSON file.

        Uses temp file + rename for atomic writes.

        Args:
            state: Import state to save
        """
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Serialize state to JSON
        state_dict = state.model_dump(mode="json")

        # Convert datetime objects to ISO format strings
        if "timestamps" in state_dict:
            timestamps = {}
            for key, value in state_dict["timestamps"].items():
                if isinstance(value, datetime):
                    timestamps[key] = value.isoformat()
                else:
                    timestamps[key] = value
            state_dict["timestamps"] = timestamps

        # Convert Path to string
        if "csv_path" in state_dict:
            state_dict["csv_path"] = str(state_dict["csv_path"])

        # Write to temp file first
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.state_file.parent, suffix=".tmp"
        )

        try:
            with open(temp_fd, "w") as f:
                json.dump(state_dict, f, indent=2)

            # Atomic rename
            Path(temp_path).rename(self.state_file)

            logger.debug(f"Saved state to {self.state_file}")

        except Exception as e:
            # Clean up temp file on error
            try:
                Path(temp_path).unlink()
            except Exception:
                pass
            raise e

    def load_state(self) -> ImportState:
        """
        Load and validate state from file.

        Returns:
            Loaded import state

        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is invalid
        """
        if not self.state_file.exists():
            raise FileNotFoundError(f"State file not found: {self.state_file}")

        try:
            with open(self.state_file) as f:
                state_dict = json.load(f)

            # Convert string timestamps back to datetime
            if "timestamps" in state_dict:
                timestamps = {}
                for key, value in state_dict["timestamps"].items():
                    if value is not None:
                        try:
                            timestamps[key] = datetime.fromisoformat(value)
                        except (ValueError, TypeError):
                            timestamps[key] = None
                    else:
                        timestamps[key] = None
                state_dict["timestamps"] = timestamps

            # Convert csv_path string to Path
            if "csv_path" in state_dict:
                state_dict["csv_path"] = Path(state_dict["csv_path"])

            state = ImportState(**state_dict)

            logger.debug(f"Loaded state from {self.state_file}")

            return state

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in state file: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to load state: {e}") from e

    def can_resume(self, state: ImportState, csv_path: Path) -> tuple[bool, str]:
        """
        Check if import can be resumed.

        Args:
            state: Import state
            csv_path: Path to CSV file

        Returns:
            Tuple of (can_resume, reason)
        """
        # Check if completed
        if state.status == ImportStatus.COMPLETED:
            return False, "Import already completed"

        # Check if CSV file matches
        if state.csv_path != csv_path:
            return False, f"CSV path mismatch: {state.csv_path} != {csv_path}"

        # Check CSV checksum
        try:
            current_checksum = compute_file_checksum(csv_path)
            if current_checksum != state.csv_checksum:
                return (
                    False,
                    "CSV file has changed (checksum mismatch)",
                )
        except Exception as e:
            return False, f"Failed to verify CSV: {e}"

        # Check if in failed state
        if state.status == ImportStatus.FAILED:
            return True, f"Can resume from failed state (phase: {state.phase.value})"

        # Check if in progress
        if state.status == ImportStatus.IN_PROGRESS:
            return True, f"Can resume from in-progress state (phase: {state.phase.value})"

        return False, f"Unknown state: {state.status}"

    def create_initial_state(
        self,
        csv_path: Path,
        table_name: str,
    ) -> ImportState:
        """
        Create initial import state.

        Args:
            csv_path: Path to CSV file
            table_name: Table name

        Returns:
            Initial import state
        """
        checksum = compute_file_checksum(csv_path)

        state = ImportState(
            csv_path=csv_path,
            csv_checksum=checksum,
            table_name=table_name,
            status=ImportStatus.PENDING,
            phase=ImportPhase.SAMPLING,
            timestamps={"started": datetime.now()},
        )

        return state

    def mark_phase_complete(
        self,
        state: ImportState,
        phase: ImportPhase,
    ) -> ImportState:
        """
        Mark a phase as complete and update state.

        Args:
            state: Current state
            phase: Phase that was completed

        Returns:
            Updated state
        """
        state.mark_phase(phase)
        self.save_state(state)
        return state

    def mark_failed(
        self,
        state: ImportState,
        error: str,
    ) -> ImportState:
        """
        Mark import as failed.

        Args:
            state: Current state
            error: Error message

        Returns:
            Updated state
        """
        state.mark_failed(error)
        self.save_state(state)
        return state

    def mark_completed(
        self,
        state: ImportState,
    ) -> ImportState:
        """
        Mark import as completed.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        state.mark_completed()
        self.save_state(state)
        return state