import fitz  # PyMuPDF
import os
import numpy as np
import argparse


def analyze_whitespace(pdf_path):
    """
    Analyze vertical whitespace between text lines to determine segmentation.
    
    Args:
        pdf_path (str): Path to the PDF file
    
    Returns:
        Tuple of (line positions, whitespace differences)
    """
    doc = fitz.open(pdf_path)
    all_line_positions = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Extract text blocks
        text_blocks = page.get_text("blocks")
        
        # Collect line positions
        page_lines = []
        for block in text_blocks:
            x0, y0, x1, y1, text = block[:5]
            if text and text.strip():
                page_lines.append({
                    'top': y0,
                    'bottom': y1,
                    'text': text.strip(),
                    'page_num': page_num
                })
        
        # Sort lines by vertical position
        page_lines.sort(key=lambda x: x['top'])
        all_line_positions.extend(page_lines)
    
    doc.close()
    
    # Analyze whitespace between lines
    whitespace_diff = []
    for i in range(1, len(all_line_positions)):
        # Calculate vertical distance between lines
        diff = abs(all_line_positions[i]['top'] - all_line_positions[i-1]['bottom'])
        whitespace_diff.append((diff, i-1, i))
    
    return all_line_positions, whitespace_diff

def segment_pdf(pdf_path: str, num_segments: int = 2, output_prefix: str = "segment_", output_dir: str = None):
    """
    Segment PDF into a specified number of segments based on whitespace analysis.
    
    Args:
        pdf_path (str): Path to the input PDF file
        num_segments (int): Number of segments to create
        output_prefix (str, optional): Prefix for output PDF files
        output_dir (str, optional): Directory to save output PDFs
    """
    # Set output directory
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(pdf_path))
    os.makedirs(output_dir, exist_ok=True)
    
    # Analyze line positions and whitespace
    line_positions, whitespace_diff = analyze_whitespace(pdf_path)

    # Sort whitespace differences 
    whitespace_diff.sort(key=lambda x: x[0])
    
    # Group whitespace by similar values
    def group_whitespace(whitespace_diff):
        groups = {}
        for diff, start_idx, end_idx in whitespace_diff:
            # Round to nearest 0.5 to group similar whitespaces
            rounded_diff = round(diff * 2) / 2
            if rounded_diff not in groups:
                groups[rounded_diff] = []
            groups[rounded_diff].append((diff, start_idx, end_idx))
        return groups
    
    whitespace_groups = group_whitespace(whitespace_diff)
    
    # Find segment boundaries
    segment_boundaries = [0]
    current_group_count = 0
    current_whitespace_group = None
    
    # Iterate through sorted whitespace groups
    sorted_groups = sorted(whitespace_groups.items(), key=lambda x: x[0])
    
    for whitespace_val, group_items in sorted_groups:
        # Stop if we've found enough segments
        if len(segment_boundaries) >= num_segments:
            break
        
        # If this is a new whitespace group, track it
        if current_whitespace_group is None:
            current_whitespace_group = whitespace_val
        
        # Count occurrences of lines with this whitespace
        for _, start_idx, end_idx in group_items:
            if start_idx not in segment_boundaries:
                segment_boundaries.append(end_idx)
                current_group_count += 1
                
                # Stop if we've reached desired number of segments
                if current_group_count >= num_segments - 1:
                    break
    
    # Ensure we have the final boundary
    if segment_boundaries[-1] != len(line_positions):
        segment_boundaries.append(len(line_positions))
    
    # Open original document
    doc = fitz.open(pdf_path)

    # Check if we have enough segments
    if len(segment_boundaries) != num_segments + 1:
        print("Unable to segment PDF into the desired number of segments. we have {} segments and need {}".format(len(segment_boundaries) - 1, num_segments))
        return
    
    # Segment PDF
    for i in range(num_segments):
        # Create output PDF
        output_pdf = fitz.open()
        
        # Get start and end indices for this segment
        start_idx = segment_boundaries[i]
        end_idx = segment_boundaries[i+1]
        
        # Create a new PDF with selected lines
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Filter lines on this page within the segment
            page_segment_lines = [
                line for line in line_positions[start_idx:end_idx]
                if line['page_num'] == page_num
            ]
            
            # If segment lines exist on this page, copy the page
            if page_segment_lines:
                new_page = output_pdf.new_page(width=page.rect.width, height=page.rect.height)
                
                # Copy relevant lines
                for line in page_segment_lines:
                    new_page.insert_text((10, line['top']), line['text'])
        
        # Save segment if it has content
        if len(output_pdf) > 0:
            output_path = os.path.join(output_dir, f"{output_prefix}{i+1}.pdf")
            output_pdf.save(output_path)
            print(f"Saved segment {i+1} to: {output_path}")
            output_pdf.close()
    
    doc.close()
    print(f"PDF segmentation completed with {num_segments} segments.")

# Example usage
if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Segment a PDF into multiple parts.")
    parser.add_argument("--input", required=True, help="Path to the input PDF file.")
    parser.add_argument("--segments", type=int, required=True, help="Number of segments to divide the PDF into.")
    parser.add_argument("--output_dir", required=True, help="Directory to save the segmented PDF files.")
    args = parser.parse_args()

    segment_pdf(args.input, args.segments, args.output_dir)
