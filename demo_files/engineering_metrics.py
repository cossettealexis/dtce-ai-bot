"""
DTCE Engineering Metrics Calculator
Calculates key performance indicators for engineering projects
"""

def calculate_team_productivity(commits, hours_worked, bugs_fixed):
    """Calculate team productivity metrics."""
    commits_per_hour = commits / hours_worked if hours_worked > 0 else 0
    bug_fix_rate = bugs_fixed / hours_worked if hours_worked > 0 else 0
    
    return {
        'commits_per_hour': commits_per_hour,
        'bug_fix_rate': bug_fix_rate,
        'productivity_score': (commits_per_hour * 10) + (bug_fix_rate * 20)
    }

def generate_project_report(project_data):
    """Generate comprehensive project status report."""
    total_stories = len(project_data['stories'])
    completed_stories = sum(1 for story in project_data['stories'] if story['status'] == 'done')
    
    completion_rate = completed_stories / total_stories if total_stories > 0 else 0
    
    return {
        'project_name': project_data['name'],
        'total_stories': total_stories,
        'completed_stories': completed_stories,
        'completion_rate': completion_rate,
        'team_size': project_data['team_size'],
        'project_health': 'green' if completion_rate > 0.8 else 'yellow' if completion_rate > 0.6 else 'red'
    }

class DTCEProjectTracker:
    """Main project tracking class for DTCE engineering teams."""
    
    def __init__(self):
        self.projects = []
        self.teams = {}
        
    def add_project(self, name, team_lead, estimated_hours):
        """Add new project to tracking system."""
        project = {
            'name': name,
            'team_lead': team_lead,
            'estimated_hours': estimated_hours,
            'actual_hours': 0,
            'status': 'planning',
            'stories': []
        }
        self.projects.append(project)
        return project
    
    def update_project_hours(self, project_name, hours):
        """Update actual hours worked on project."""
        for project in self.projects:
            if project['name'] == project_name:
                project['actual_hours'] += hours
                break
