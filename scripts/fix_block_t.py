#!/usr/bin/env python3
"""Apply Block T replacement in automation_manager.py."""

PATH = '/home/pete/Documents/projects/News Intelligence/api/services/automation_manager.py'

with open(PATH) as f:
    text = f.read()

# Block T: conn_check block for confidence recheck after processing
old = (
    '                            conn_check = await self._get_db_connection()\n'
    '                            cursor_check = conn_check.cursor()\n'
    '                            cursor_check.execute(\n'
    '                                f"""\n'
    '                                SELECT COALESCE(AVG(confidence_score), 0.0) as avg_confidence\n'
    '                                FROM {schema_name}.article_topic_assignments\n'
    '                                WHERE article_id = %s\n'
    '                            """,\n'
    '                                (article_id,),\n'
    '                            )\n'
    '                            result_row = cursor_check.fetchone()\n'
    '                            new_confidence = (\n'
    '                                float(result_row[0]) if result_row and result_row[0] else 0.0\n'
    '                            )\n'
    '                            cursor_check.close()\n'
    '                            conn_check.close()\n'
)

if old not in text:
    print("ERROR: Block T source pattern not found")
    # Show what we're looking for
    print(f"Looking for {len(old)} char block...")
    exit(1)

replacement = (
    '                    async with self._db_conn_ctx() as conn:\n'
    '                        cursor_check = conn.cursor()\n'
    '                        cursor_check.execute(\n'
    '                            f"""\n'
    '                            SELECT COALESCE(AVG(confidence_score), 0.0) as avg_confidence\n'
    '                            FROM {schema_name}.article_topic_assignments\n'
    '                            WHERE article_id = %s\n'
    '                        """,\n'
    '                            (article_id,),\n'
    '                        )\n'
    '                        result_row = cursor_check.fetchone()\n'
    '                        new_confidence = (\n'
    '                            float(result_row[0]) if result_row and result_row[0] else 0.0\n'
    '                        )\n'
)

if text.count(old) != 1:
    print(f"ERROR: Block T not unique ({text.count(old)} occurrences)")
    exit(1)

text = text.replace(old, replacement, 1)

with open(PATH, 'w') as f:
    f.write(text)

print(f"Block T applied. Lines now: {text.count(chr(10))}")