import pandas as pd
import numpy as np
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import cv2
import base64
from io import BytesIO
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

class InteractiveHeatmapGenerator:
    def __init__(self, csv_path):
        """
        Initialize heatmap generator with cursor data
        
        Args:
            csv_path: Path to your CSV file
        """
        self.df = pd.read_csv(csv_path)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df.sort_values('timestamp', inplace=True)
        
    def preprocess_url_data(self, target_url, session_threshold_minutes=30):
        """
        Process data for a specific URL with session segmentation
        
        Args:
            target_url: URL to analyze
            session_threshold_minutes: Minutes between events to consider new session
        """
        # Filter for target URL
        url_data = self.df[self.df['url'] == target_url].copy()
        
        if url_data.empty:
            raise ValueError(f"No data found for URL: {target_url}")
        
        # Create session IDs based on time gaps
        url_data['time_diff'] = url_data['timestamp'].diff()
        url_data['new_session'] = url_data['time_diff'] > pd.Timedelta(minutes=session_threshold_minutes)
        url_data['session_id'] = url_data['new_session'].cumsum()
        
        # Calculate adjusted coordinates considering zoom, scroll, and viewport
        url_data = self._calculate_absolute_coordinates(url_data)
        
        return url_data
    
    def _calculate_absolute_coordinates(self, df):
        """
        Calculate absolute screen coordinates considering all factors
        """
        # Handle zoom (assuming zoom level affects page coordinates)
        # If you have zoom data, adjust coordinates here
        # For now, we'll assume no zoom or it's accounted for in x_page/y_page
        
        # Adjust for scroll
        df['x_absolute'] = df['x_page'] + df['scrollX']
        df['y_absolute'] = df['y_page'] + df['scrollY']
        
        # Normalize coordinates to a standard viewport if needed
        # This helps compare different viewport sizes
        if 'viewportW' in df.columns and 'viewportH' in df.columns:
            # Convert to percentage of page
            df['x_normalized'] = df['x_absolute'] / df['docWidth']
            df['y_normalized'] = df['y_absolute'] / df['docHeight']
        
        return df
    
    def generate_density_heatmap(self, url_data, output_type='interactive'):
        """
        Generate a density-based heatmap
        
        Args:
            url_data: Preprocessed DataFrame for the URL
            output_type: 'interactive' (plotly) or 'static' (matplotlib)
        """
        # Extract coordinates
        x_coords = url_data['x_absolute'].values
        y_coords = url_data['y_absolute'].values
        
        # Get page dimensions
        page_width = int(url_data['docWidth'].iloc[0])
        page_height = int(url_data['docHeight'].iloc[0])
        
        # Create density grid
        grid_size = 10  # pixels per grid cell
        grid_x = int(page_width / grid_size)
        grid_y = int(page_height / grid_size)
        
        # Create density matrix
        density = np.zeros((grid_y, grid_x))
        
        for x, y in zip(x_coords, y_coords):
            if 0 <= x < page_width and 0 <= y < page_height:
                grid_col = min(int(x / grid_size), grid_x - 1)
                grid_row = min(int(y / grid_size), grid_y - 1)
                density[grid_row, grid_col] += 1
        
        # Apply Gaussian filter for smoother heatmap
        density = gaussian_filter(density, sigma=1.5)
        
        if output_type == 'interactive':
            return self._create_plotly_heatmap(density, grid_size, url_data)
        else:
            return self._create_matplotlib_heatmap(density, grid_size, url_data)
    
    def _create_plotly_heatmap(self, density, grid_size, url_data):
        """
        Create interactive Plotly heatmap
        """
        # Create heatmap trace
        heatmap = go.Heatmap(
            z=density,
            colorscale='Hot',
            showscale=True,
            hoverinfo='z',
            opacity=0.7
        )
        
        # Get additional data for tooltips
        page_width = int(url_data['docWidth'].iloc[0])
        page_height = int(url_data['docHeight'].iloc[0])
        
        # Create figure
        fig = go.Figure(data=heatmap)
        
        # Update layout
        fig.update_layout(
            title=f"Cursor Heatmap - {len(url_data)} interactions",
            width=page_width,
            height=page_height,
            xaxis=dict(
                range=[0, density.shape[1]],
                showgrid=False,
                zeroline=False,
                visible=False
            ),
            yaxis=dict(
                range=[0, density.shape[0]],
                scaleanchor="x",
                scaleratio=1,
                showgrid=False,
                zeroline=False,
                visible=False
            ),
            hovermode='closest'
        )
        
        return fig
    
    def generate_element_interaction_map(self, url_data):
        """
        Generate a visualization showing which elements were interacted with most
        """
        # Count interactions by element type and selector
        element_interactions = url_data.groupby(['tagName', 'selector', 'className', 'id']).size().reset_index(name='count')
        element_interactions = element_interactions.sort_values('count', ascending=False)
        
        # Create bar chart
        fig = go.Figure()
        
        # Top 20 elements
        top_elements = element_interactions.head(20)
        
        # Create labels
        labels = []
        for _, row in top_elements.iterrows():
            label = f"{row['tagName']}"
            if pd.notna(row['className']) and row['className']:
                label += f".{row['className']}"
            if pd.notna(row['id']) and row['id']:
                label += f"#{row['id']}"
            labels.append(label)
        
        fig.add_trace(go.Bar(
            x=top_elements['count'],
            y=labels,
            orientation='h',
            marker=dict(
                color=top_elements['count'],
                colorscale='Viridis',
                showscale=True
            )
        ))
        
        fig.update_layout(
            title="Most Interacted Elements",
            xaxis_title="Number of Interactions",
            height=600
        )
        
        return fig
    
    def create_timeline_heatmap(self, url_data, time_bin='1H'):
        """
        Create heatmap showing interaction patterns over time
        """
        # Resample by time
        url_data.set_index('timestamp', inplace=True)
        time_series = url_data.resample(time_bin).size()
        
        fig = go.Figure(data=go.Scatter(
            x=time_series.index,
            y=time_series.values,
            mode='lines+markers',
            fill='tozeroy',
            line=dict(color='orange', width=2),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Interaction Timeline",
            xaxis_title="Time",
            yaxis_title="Interactions per hour",
            hovermode='x'
        )
        
        return fig
    
    def generate_html_report(self, target_url, output_path='heatmap_report.html'):
        """
        Generate comprehensive HTML report with multiple visualizations
        """
        # Process data
        url_data = self.preprocess_url_data(target_url)
        
        # Generate all visualizations
        density_fig = self.generate_density_heatmap(url_data, 'interactive')
        element_fig = self.generate_element_interaction_map(url_data)
        timeline_fig = self.create_timeline_heatmap(url_data)
        
        # Get statistics
        stats = self._calculate_statistics(url_data)
        
        # Generate HTML
        html_content = self._create_html_template(
            target_url, 
            density_fig, 
            element_fig, 
            timeline_fig, 
            stats
        )
        
        # Save HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Report saved to: {output_path}")
        return output_path
    
    def _calculate_statistics(self, url_data):
        """
        Calculate various statistics about the interactions
        """
        stats = {
            'total_interactions': len(url_data),
            'unique_users': url_data['session_id'].nunique(),
            'interaction_types': url_data['type'].value_counts().to_dict(),
            'avg_session_duration': None,
            'most_active_hour': url_data['timestamp'].dt.hour.mode()[0] if not url_data.empty else None,
            'top_element': url_data['tagName'].mode()[0] if not url_data.empty else None,
            'avg_x': url_data['x_absolute'].mean(),
            'avg_y': url_data['y_absolute'].mean()
        }
        
        # Calculate session durations
        session_durations = []
        for session_id in url_data['session_id'].unique():
            session_data = url_data[url_data['session_id'] == session_id]
            if len(session_data) > 1:
                duration = (session_data['timestamp'].max() - session_data['timestamp'].min()).total_seconds()
                session_durations.append(duration)
        
        if session_durations:
            stats['avg_session_duration'] = np.mean(session_durations)
        
        return stats
    
    def _create_html_template(self, url, density_fig, element_fig, timeline_fig, stats):
        """
        Create HTML template for the report
        """
        # Convert Plotly figures to HTML
        density_html = density_fig.to_html(full_html=False, include_plotlyjs='cdn')
        element_html = element_fig.to_html(full_html=False, include_plotlyjs=False)
        timeline_html = timeline_fig.to_html(full_html=False, include_plotlyjs=False)
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Heatmap Analysis - {url}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                .header {{
                    background-color: #333;
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .stat-value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #2196F3;
                }}
                .stat-label {{
                    font-size: 14px;
                    color: #666;
                }}
                .visualization {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }}
                h2 {{
                    color: #333;
                    border-bottom: 2px solid #2196F3;
                    padding-bottom: 10px;
                }}
                .url-display {{
                    font-family: monospace;
                    background-color: #f0f0f0;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                    overflow-x: auto;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Interactive Heatmap Analysis</h1>
                    <p class="url-display">URL: {url}</p>
                    <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{stats['total_interactions']}</div>
                        <div class="stat-label">Total Interactions</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{stats['unique_users']}</div>
                        <div class="stat-label">Unique Sessions</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{len(stats['interaction_types'])}</div>
                        <div class="stat-label">Interaction Types</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{stats['most_active_hour'] or 'N/A'}:00</div>
                        <div class="stat-label">Most Active Hour</div>
                    </div>
                </div>
                
                <div class="visualization">
                    <h2>📈 Interaction Density Heatmap</h2>
                    <p>Shows where users interacted most on the page</p>
                    <div id="density-heatmap">{density_html}</div>
                </div>
                
                <div class="visualization">
                    <h2>🔍 Element Interaction Analysis</h2>
                    <p>Most frequently interacted elements</p>
                    <div id="element-analysis">{element_html}</div>
                </div>
                
                <div class="visualization">
                    <h2>⏰ Interaction Timeline</h2>
                    <p>Interaction patterns over time</p>
                    <div id="timeline">{timeline_html}</div>
                </div>
                
                <div class="visualization">
                    <h2>📋 Detailed Statistics</h2>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div>
                            <h3>Interaction Types</h3>
                            <ul>
                                {"".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in stats['interaction_types'].items()])}
                            </ul>
                        </div>
                        <div>
                            <h3>Coordinate Analysis</h3>
                            <p><strong>Average X Position:</strong> {stats['avg_x']:.1f}px</p>
                            <p><strong>Average Y Position:</strong> {stats['avg_y']:.1f}px</p>
                            <p><strong>Most Common Element:</strong> {stats['top_element'] or 'N/A'}</p>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def export_to_web_overlay(self, target_url, output_dir='heatmap_overlay'):
        """
        Export data for use with web-based heatmap overlay
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        url_data = self.preprocess_url_data(target_url)
        
        # Prepare data for heatmap.js format
        heatmap_data = {
            "max": 1,
            "data": []
        }
        
        # Normalize coordinates for overlay
        page_width = int(url_data['docWidth'].iloc[0])
        page_height = int(url_data['docHeight'].iloc[0])
        
        for _, row in url_data.iterrows():
            # Convert to percentage for responsive overlay
            x_percent = (row['x_absolute'] / page_width) * 100
            y_percent = (row['y_absolute'] / page_height) * 100
            
            heatmap_data["data"].append({
                "x": x_percent,
                "y": y_percent,
                "value": 1,
                "type": row['type'],
                "element": row['tagName'],
                "timestamp": row['timestamp'].isoformat()
            })
        
        # Save data
        data_path = os.path.join(output_dir, 'heatmap_data.json')
        with open(data_path, 'w') as f:
            json.dump(heatmap_data, f, indent=2)
        
        # Create overlay HTML
        overlay_html = self._create_overlay_html(page_width, page_height)
        overlay_path = os.path.join(output_dir, 'overlay.html')
        with open(overlay_path, 'w') as f:
            f.write(overlay_html)
        
        print(f"Heatmap overlay exported to: {output_dir}/")
        print(f"Data: {data_path}")
        print(f"Overlay: {overlay_path}")
        
        return data_path, overlay_path
    
    def _create_overlay_html(self, page_width, page_height):
        """
        Create HTML file for heatmap overlay
        """
        return f"""
        <!DOCTYPE html>
        <html>
    <head>
        <title>Heatmap Overlay</title>
        <script src="https://cdn.jsdelivr.net/npm/heatmap.js@2.0.5/build/heatmap.min.js"></script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                position: relative;
                width: {page_width}px;
                height: {page_height}px;
                background-color: #f0f0f0;
            }}
            #heatmapContainer {{
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: 1000;
                pointer-events: none;
            }}
            #controls {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 2000;
            }}
            .control-group {{
                margin-bottom: 10px;
            }}
            label {{
                display: block;
                margin-bottom: 5px;
                font-weight: bold;
            }}
            input[type="range"] {{
                width: 200px;
            }}
        </style>
    </head>
    <body>
        <!-- This would be your webpage content or screenshot -->
        <div id="heatmapContainer"></div>
        
        <div id="controls">
            <h3>Heatmap Controls</h3>
            <div class="control-group">
                <label for="opacity">Opacity: <span id="opacityValue">0.6</span></label>
                <input type="range" id="opacity" min="0" max="1" step="0.1" value="0.6">
            </div>
            <div class="control-group">
                <label for="radius">Radius: <span id="radiusValue">50</span></label>
                <input type="range" id="radius" min="10" max="200" value="50">
            </div>
            <div class="control-group">
                <label for="blur">Blur: <span id="blurValue">0.85</span></label>
                <input type="range" id="blur" min="0" max="1" step="0.05" value="0.85">
            </div>
            <button id="toggleHeatmap">Toggle Heatmap</button>
        </div>

        <script>
            // Initialize heatmap
            var heatmapInstance = h337.create({{
                container: document.getElementById('heatmapContainer'),
                radius: 50,
                maxOpacity: 0.6,
                minOpacity: 0,
                blur: 0.85
            }});
            
            // Load data
            fetch('heatmap_data.json')
                .then(response => response.json())
                .then(data => {{
                    heatmapInstance.setData(data);
                }});
            
            // Controls
            document.getElementById('opacity').addEventListener('input', function(e) {{
                document.getElementById('opacityValue').textContent = e.target.value;
                heatmapInstance.configure({{
                    maxOpacity: parseFloat(e.target.value)
                }});
            }});
            
            document.getElementById('radius').addEventListener('input', function(e) {{
                document.getElementById('radiusValue').textContent = e.target.value;
                heatmapInstance.configure({{
                    radius: parseInt(e.target.value)
                }});
            }});
            
            document.getElementById('blur').addEventListener('input', function(e) {{
                document.getElementById('blurValue').textContent = e.target.value;
                heatmapInstance.configure({{
                    blur: parseFloat(e.target.value)
                }});
            }});
            
            document.getElementById('toggleHeatmap').addEventListener('click', function() {{
                var container = document.getElementById('heatmapContainer');
                container.style.display = container.style.display === 'none' ? 'block' : 'none';
            }});
        </script>
    </body>
    </html>
        """

# Usage Example
def main():
    # Initialize generator
    generator = InteractiveHeatmapGenerator('./data/Ala/events.csv')
    
    # Target URL to analyze
    target_url = "https://letterboxd.com/"
    
    try:
        # Option 1: Generate complete HTML report
        report_path = generator.generate_html_report(
            target_url=target_url,
            output_path='heatmap_analysis.html'
        )
        
        # Option 2: Export for web overlay
        # generator.export_to_web_overlay(target_url, 'overlay_data')
        
        # Option 3: Get just the density heatmap
        # url_data = generator.preprocess_url_data(target_url)
        # fig = generator.generate_density_heatmap(url_data, 'interactive')
        # fig.show()
        
        print(f"Analysis complete! Report saved to: {report_path}")
        
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()