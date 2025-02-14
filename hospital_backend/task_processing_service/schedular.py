from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import logging
from django.core.cache import cache
from django.conf import settings


class StateScheduler:
    def __init__(self, db_manager: Any, logger: logging.Logger):
        self.db_manager = db_manager
        self.logger = logger

    def _get_cache_key(self, note_id: str, patient_id: str) -> str:
        """Generate cache key for storing scheduling state."""
        return f"schedule:{note_id}:{patient_id}"

    def _calculate_next_occurrence(self, schedule: Dict[str, Any],
                                   last_completion: Optional[datetime]) -> datetime | None:
        """Calculate next occurrence based on schedule type and last completion."""
        now = datetime.utcnow()

        # If never completed or completed on a different day
        if not last_completion or last_completion.date() < now.date():
            if schedule['type'] == 'fixed_time':
                # Set specific_times to an empty list if missing
                specific_times = schedule.get('specific_times', [])
                if not specific_times:
                    return None  # No specific times provided, so no next occurrence

                # Validate specific_times format
                if not isinstance(specific_times, list):
                    raise ValueError("specific_times must be a list")
                if not all(isinstance(time_str, str) for time_str in specific_times):
                    raise ValueError("specific_times must be a list of strings")

                # Find next available time today
                for time_str in specific_times:
                    try:
                        hour, minute = map(int, time_str.split(':'))
                        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if next_time > now:
                            return next_time
                    except (ValueError, IndexError):
                        raise ValueError(f"Invalid time format in specific_times: {time_str}. Expected 'HH:MM'.")

                # If no times left today, use first time tomorrow
                try:
                    hour, minute = map(int, specific_times[0].split(':'))
                    tomorrow = now + timedelta(days=1)
                    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid time format in specific_times: {specific_times[0]}. Expected 'HH:MM'.")

            elif schedule['type'] == 'interval_based':
                # Set interval_hours to 0 if missing
                interval_hours = schedule.get('interval_hours', 0)
                if interval_hours <= 0:
                    return None  # No interval provided, so no next occurrence
                return now + timedelta(hours=interval_hours)

            elif schedule['type'] == 'frequency_based':
                # Set times_per_day to 0 if missing
                times_per_day = schedule.get('times_per_day', 0)
                if times_per_day <= 0:
                    return None  # No frequency provided, so no next occurrence
                # Calculate interval based on times_per_day
                hours_interval = 12 / times_per_day  # 12 hour day (8AM-8PM)
                return now + timedelta(hours=hours_interval)

        return None  # No more occurrences needed today

    def store_schedule_state(self, note_id: str, patient_id: str,
                             description: str, schedule: Dict[str, Any]) -> None:
        """Store scheduling state in MongoDB and set next occurrence in Redis."""
        try:
            collection = self.db_manager.get_collection("schedule_states")
            state = {
                "note_id": note_id,
                "patient_id": patient_id,
                "description": description,
                "schedule": schedule,
                "total_occurrences": schedule['duration'],
                "completed_occurrences": 0,
                "last_completion": None,
                "is_active": True,
                "created_at": datetime.utcnow()
            }

            collection.update_one(
                {"note_id": note_id},
                {"$set": state},
                upsert=True
            )

            next_occurrence = self._calculate_next_occurrence(schedule, None)
            if next_occurrence:
                print("TTTTTTTTTTTTTTTTTTTTTTTT")
                cache_key = self._get_cache_key(note_id, patient_id)
                cache_data = {
                    "next_occurrence": next_occurrence.isoformat(),
                    "description": description
                }
                # Set with 24 hour expiry
                cache.set(cache_key, json.dumps(cache_data), timeout=86400)

            self.logger.info(f"Stored schedule state for note {note_id}")

        except Exception as e:
            self.logger.error(f"Error storing schedule state: {e}")
            raise

    def mark_completed(self, note_id: str, patient_id: str, step_id: str) -> None:
        """Mark a schedule as completed and update next occurrence."""
        try:
            collection = self.db_manager.get_collection("schedule_states")
            now = datetime.utcnow()

            result = collection.find_one_and_update(
                {"note_id": note_id, "step_id": step_id, "is_active": True},
                {
                    "$inc": {"completed_occurrences": 1},
                    "$set": {"last_completion": now}
                },
                return_document=True
            )

            if not result:
                raise ValueError(f"No active schedule found for note {note_id}")

            if result['completed_occurrences'] >= result['total_occurrences']:
                collection.update_one(
                    {"_id": result['_id']},
                    {"$set": {"is_active": False}}
                )
                cache_key = self._get_cache_key(note_id, patient_id)
                cache.delete(cache_key)
                return

            next_occurrence = self._calculate_next_occurrence(result['schedule'], now)
            if next_occurrence:
                cache_key = self._get_cache_key(note_id, patient_id)
                cache_data = {
                    "next_occurrence": next_occurrence.isoformat(),
                    "description": result['description']
                }
                cache.set(cache_key, json.dumps(cache_data), timeout=86400)

            self.logger.info(f"Marked completion for note {note_id}, step {step_id}")

        except Exception as e:
            self.logger.error(f"Error marking completion: {e}")
            raise

    def get_due_notifications(self, note_id: str, patient_id: str) -> List[Dict[str, Any]]:
        """Get all due notifications for a specific note and patient from cache."""
        try:
            now = datetime.utcnow()
            cache_key = self._get_cache_key(note_id, patient_id)
            data = cache.get(cache_key)

            if not data:
                self.logger.warning(f"No notifications found in cache for {cache_key}")
                return []

            schedule_data = json.loads(data)
            next_occurrence = datetime.fromisoformat(schedule_data['next_occurrence'])
            self.logger.info(f"Checking notification {cache_key} - Next: {next_occurrence}, Now: {now}")

            if next_occurrence <= now:
                return [{
                    "note_id": note_id,
                    "patient_id": patient_id,
                    "description": schedule_data['description']
                }]
            else:
                self.logger.info(f"Notification {cache_key} is NOT due yet.")

            return []

        except Exception as e:
            self.logger.error(f"Error getting due notifications: {e}")
            raise

    def cancel_note_schedules(self, note_id: str) -> None:
        """Cancel all schedules for a specific note."""
        try:
            collection = self.db_manager.get_collection("schedule_states")
            collection.update_many(
                {"note_id": note_id, "is_active": True},
                {"$set": {"is_active": False}}
            )

            # Retrieve stored keys list instead of using cache.keys()
            cache_key_list_name = f"schedule:{note_id}:keys"
            all_keys = cache.get(cache_key_list_name, [])

            if all_keys:
                cache.delete_many(all_keys)
                cache.delete(cache_key_list_name)  # Remove the tracking list

            self.logger.info(f"Cancelled all schedules for note {note_id}")

        except Exception as e:
            self.logger.error(f"Error cancelling note schedules: {e}")
            raise
