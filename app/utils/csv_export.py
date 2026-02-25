"""
CSV export utilities
"""
import csv
import io
from typing import Iterable, Dict, List
from fastapi.responses import StreamingResponse


def stream_csv(headers: List[str], rows: Iterable[Dict], filename: str = "export.csv") -> StreamingResponse:
    """
    Stream CSV data as HTTP response
    
    Args:
        headers: List of column headers
        rows: Iterable of dictionaries with data rows
        filename: Filename for Content-Disposition header
    
    Returns:
        StreamingResponse with CSV content
    """
    def generate():
        # Create StringIO buffer for CSV writing
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        
        # Write headers
        writer.writeheader()
        content = output.getvalue()
        output.seek(0)
        output.truncate(0)
        yield content
        
        # Write rows
        for row in rows:
            # Ensure all headers are present in row (fill missing with empty string)
            row_data = {header: str(row.get(header, "")) for header in headers}
            writer.writerow(row_data)
            content = output.getvalue()
            output.seek(0)
            output.truncate(0)
            yield content
    
    response = StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
    
    return response
