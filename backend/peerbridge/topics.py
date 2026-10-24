"""Persistent topic catalog shared by validation, rules, and semantic matching."""
import json
import sqlite3
from . import db

DEFAULT_TOPICS = [{'id': 'algebra',
  'label': 'Algebra',
  'keywords': ['algebra',
               'equation',
               'equations',
               'variable',
               'variables',
               'letters',
               'solve for',
               'linear',
               'quadratic'],
  'description': 'introductory algebra equations with letters variables linear equations '
                 'mathematical expressions'},
 {'id': 'geometry',
  'label': 'Geometry',
  'keywords': ['geometry',
               'triangle',
               'triangles',
               'angles',
               'perimeter',
               'area',
               'circle',
               'proof',
               'shapes'],
  'description': 'geometry triangles angles circles shapes area perimeter geometric proofs'},
 {'id': 'python',
  'label': 'Python',
  'keywords': ['python',
               'coding',
               'programming',
               'code',
               'debug',
               'loop',
               'loops',
               'function',
               'functions',
               'list',
               'lists'],
  'description': 'Python computer programming code functions loops lists software debugging'},
 {'id': 'robotics',
  'label': 'Robotics',
  'keywords': ['robot', 'robots', 'robotics', 'sensor', 'sensors', 'motor', 'motors', 'arduino'],
  'description': 'robotics building robots motors sensors electronics robot engineering'},
 {'id': 'writing',
  'label': 'Writing',
  'keywords': ['writing',
               'essay',
               'essays',
               'paragraph',
               'grammar',
               'revision',
               'story',
               'stories',
               'write'],
  'description': 'essay writing paragraphs grammar revision creative writing literature'},
 {'id': 'presentations',
  'label': 'Presentations',
  'keywords': ['presentation',
               'presentations',
               'public speaking',
               'speech',
               'speeches',
               'audience',
               'speaking',
               'talk in class'],
  'description': 'public speaking presentations speech audience confidence giving a talk'},
 {'id': 'science',
  'label': 'Science',
  'keywords': ['science',
               'biology',
               'chemistry',
               'cells',
               'experiment',
               'lab',
               'photosynthesis',
               'plants'],
  'description': 'science biology chemistry experiments scientific method cells plants lab'},
 {'id': 'physics',
  'label': 'Physics',
  'keywords': ['physics',
               'forces',
               'force',
               'motion',
               'velocity',
               'gravity',
               'energy',
               'mechanics',
               'acceleration'],
  'description': 'physics mechanics forces motion velocity energy gravity electricity'},
 {'id': 'study_skills',
  'label': 'Study skills',
  'keywords': ['study',
               'studying',
               'organize',
               'organizing',
               'organisation',
               'organization',
               'homework',
               'procrastination',
               'time management',
               'exam',
               'exams',
               'notes',
               'planning'],
  'description': 'study skills time management homework organization revision planning exams '
                 'notes'},
 {'id': 'school_transition',
  'label': 'School transition',
  'keywords': ['new school',
               'new to',
               'do not know anyone',
               "don't know anyone",
               'making friends',
               'make friends',
               'school club',
               'school clubs',
               'belong',
               'lonely',
               'welcome',
               'transition',
               'new student',
               'new here'],
  'description': 'new school making friends belonging welcome activities school transition peer '
                 'guide'}]


def seed_topics(conn):
    for topic in DEFAULT_TOPICS:
        conn.execute("INSERT OR IGNORE INTO topics(id,label,keywords,description) VALUES(?,?,?,?)",
                     (topic['id'], topic['label'], json.dumps(topic['keywords']), topic['description']))


def list_topics():
    with db.connect() as conn:
        try:
            rows = conn.execute("SELECT id,label,keywords,description FROM topics ORDER BY rowid").fetchall()
        except sqlite3.OperationalError as exc:
            # Standalone model/evaluation use before application startup.
            if 'no such table' in str(exc):
                return [dict(topic) for topic in DEFAULT_TOPICS]
            raise
        return [dict(row, keywords=json.loads(row['keywords'])) for row in rows] or [dict(topic) for topic in DEFAULT_TOPICS]


def topic_ids():
    return tuple(topic['id'] for topic in list_topics())


def topic_descriptions():
    return {topic['id']: topic['description'] for topic in list_topics()}
