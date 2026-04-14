from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
import streamlit as st

from core.database import clear_app_caches, get_sb, load_profile_row
from core.i18n import t
from core.state import get_current_user_id, with_owner
from helpers.archive_utils import ARCHIVED_STATUS, filter_archived_rows, is_archived_status
from helpers.generation_guidance import build_expert_panel_prompt_blurb

AI_PROGRAM_DAILY_LIMIT = 1
AI_PROGRAM_COOLDOWN_SECONDS = 10
AI_PROGRAM_LIMITS_ENABLED = False


def _lp():
    import helpers.lesson_planner as lp

    return lp


def _wb():
    import helpers.worksheet_builder as wb

    return wb


def _eb():
    import helpers.quick_exam_builder as eb

    return eb


def _tsi():
    import helpers.teacher_student_integration as tsi

    return tsi


PROGRAM_SOURCE_TYPES = ["classio", "ai", "custom"]
PROGRAM_VISIBILITY_OPTIONS = ["private", "public"]
PROGRAM_STATUS_OPTIONS = ["draft", "active", "archived"]
PROGRAM_ASSIGNMENT_STATUS = ["assigned", "in_progress", "completed", "archived"]

_LANGUAGE_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
_ACADEMIC_LEVEL_ORDER = ["beginner_band", "intermediate_band", "advanced_band"]


_STAGE_STRUCTURE_RULES = {
    "early_primary": {"units_default": 8, "units_min": 6, "units_max": 8, "lessons_default": 4, "lessons_min": 3, "lessons_max": 5},
    "upper_primary": {"units_default": 10, "units_min": 8, "units_max": 11, "lessons_default": 4, "lessons_min": 3, "lessons_max": 5},
    "lower_secondary": {"units_default": 10, "units_min": 8, "units_max": 11, "lessons_default": 4, "lessons_min": 3, "lessons_max": 6},
    "upper_secondary": {"units_default": 11, "units_min": 9, "units_max": 12, "lessons_default": 4, "lessons_min": 3, "lessons_max": 6},
    "adult_stage": {"units_default": 10, "units_min": 8, "units_max": 12, "lessons_default": 4, "lessons_min": 3, "lessons_max": 6},
}

_ENGINE_STRUCTURE_OVERRIDES = {
    "language": {
        "adult_stage": {"units_default": 11, "units_min": 8, "units_max": 12, "lessons_default": 4, "lessons_min": 3, "lessons_max": 5},
    },
    "study_skills": {
        "adult_stage": {"units_default": 8, "units_min": 6, "units_max": 10, "lessons_default": 3, "lessons_min": 2, "lessons_max": 4},
    },
}

_SUBJECT_GUIDANCE = {
    "language": {
        "frameworks": ["CEFR", "spiraled skills progression", "balanced input and output", "recycling and retrieval practice"],
        "principles": [
            "Sequence listening, speaking, reading, writing, grammar, and vocabulary in a balanced way.",
            "Revisit high-value language across units instead of treating topics as one-off.",
            "Make outcomes communicative and visible to the learner.",
            "Keep grammar and vocabulary in service of communication, not isolated coverage.",
        ],
    },
    "math": {
        "frameworks": ["scope and sequence", "concrete-representational-abstract progression", "retrieval and spaced review"],
        "principles": [
            "Respect prerequisite knowledge and conceptual build-up.",
            "Interleave fluency, reasoning, and application over time.",
            "Avoid jumping across concepts without cumulative review.",
            "Include checkpoints for misconceptions and worked examples.",
        ],
    },
    "science": {
        "frameworks": ["inquiry-based science", "phenomenon-based learning", "concept progression"],
        "principles": [
            "Anchor units in observable phenomena and scientific thinking.",
            "Sequence vocabulary, concepts, evidence, and explanation carefully.",
            "Use practice and assessment tasks that check both understanding and reasoning.",
            "Keep the load age-appropriate and avoid over-packing units.",
        ],
    },
    "music": {
        "frameworks": ["spiraled musicianship", "performance-practice-review cycle", "technical plus expressive balance"],
        "principles": [
            "Balance theory, listening, performance, and review.",
            "Sequence skills from imitation to independence.",
            "Keep repeated rehearsal opportunities inside the program.",
            "Use clear performance checkpoints and manageable repertoire load.",
        ],
    },
    "study_skills": {
        "frameworks": ["metacognition", "self-regulated learning", "habit formation"],
        "principles": [
            "Sequence routines before advanced independence tasks.",
            "Make outcomes practical and immediately usable by the student.",
            "Build reflection and transfer into every unit.",
            "Favor consistency and repeatable structures over overloaded unit plans.",
        ],
    },
    "general": {
        "frameworks": ["backward design", "spiraled review", "age-appropriate scope and sequence"],
        "principles": [
            "Move from foundation to application with clear dependency logic.",
            "Keep lesson purposes varied but coherent across the unit.",
            "Use repeated review and cumulative checks.",
            "Make the sequence practical for real teaching calendars.",
        ],
    },
}

_SUBJECT_FAMILY_KEYWORDS = {
    "language": [
        "english", "spanish", "french", "german", "italian", "turkish", "arabic", "language",
        "esl", "efl", "reading", "writing", "speaking", "listening", "phonics", "literacy",
        "grammar", "vocabulary", "conversation",
    ],
    "math": [
        "math", "mathematics", "algebra", "geometry", "fractions", "calculus", "statistics",
        "numeracy", "arithmetic", "trigonometry",
    ],
    "science": [
        "science", "biology", "chemistry", "physics", "stem", "geology", "astronomy",
        "environmental", "lab", "scientific",
    ],
    "music": [
        "music", "piano", "violin", "guitar", "singing", "choir", "rhythm", "solfege",
        "composition", "instrument",
    ],
    "study_skills": [
        "study skills", "executive function", "learning skills", "organization", "focus",
        "revision", "memory", "homework", "metacognition", "productivity",
    ],
    "general": [
        "history", "geography", "social studies", "economics", "philosophy", "art", "drama",
        "business", "coding", "computer", "ict", "robotics", "psychology",
    ],
}

_DELIVERY_GUIDANCE = {
    "online": [
        "Prefer concise task cycles, visible routines, and interaction every few minutes.",
        "Replace hands-on tasks with camera-based demos, digital whiteboards, breakout talk, annotation, or household materials when needed.",
        "Design speaking, collaboration, and checking-for-understanding intentionally because attention drifts faster online.",
    ],
    "offline": [
        "Use movement, manipulatives, pair work, stations, notebooks, boardwork, and physical modeling when pedagogically useful.",
        "Plan transitions, pacing, and materials realistically so activities are manageable in a live room.",
        "Use oral rehearsal, teacher circulation, and peer support to surface misconceptions quickly.",
    ],
    "blended": [
        "Separate what must happen live from what can happen asynchronously.",
        "Use Classio resources for structured practice and use offline or live moments for discussion, speaking, experimentation, and performance.",
    ],
}

_NON_CLASSIO_ACTIVITY_BANK = {
    "language": ["speaking task", "pair dialogue", "role play", "mini presentation", "dictation", "listening from teacher voice"],
    "math": ["manipulative exploration", "whiteboard reasoning", "math talk", "real-world problem task", "error analysis discussion"],
    "science": ["hands-on experiment", "observation log", "phenomenon discussion", "teacher demo", "classification lab", "claim-evidence-reasoning talk"],
    "music": ["performance task", "call and response", "aural discrimination", "teacher modeling", "rhythm drill", "ensemble practice"],
    "study_skills": ["routine rehearsal", "reflection conference", "planner setup", "self-check protocol", "study simulation"],
    "general": ["project task", "discussion circle", "research mini-task", "presentation", "visual organizer", "peer critique"],
}

_SUBJECT_PROGRESSION_PROFILES = {
    "english": {
        "global_priorities": [
            "Build communication, not isolated content coverage.",
            "Sequence receptive and productive skills together with spiraled grammar and vocabulary.",
            "Use CEFR-style can-do outcomes and recycle language systematically.",
        ],
        "by_stage": {
            "early_primary": {
                "A1": {
                    "focus_strands": ["phonological awareness", "high-frequency vocabulary", "classroom language", "listening and speaking routines", "early reading and writing"],
                    "sequence_expectations": [
                        "Start with oral comprehension, classroom routines, songs, chants, and concrete vocabulary.",
                        "Move from recognition to supported production through repetition, visuals, and sentence frames.",
                        "Introduce reading and writing gradually through short words, phrases, and patterned texts.",
                    ],
                },
            },
            "upper_primary": {
                "A1": {
                    "focus_strands": ["everyday vocabulary", "basic grammar in context", "reading for gist", "guided speaking", "sentence-level writing"],
                    "sequence_expectations": [
                        "Start with identity, family, school, routines, and immediate world topics.",
                        "Build from single-sentence understanding to short exchanges, paragraph reading, and simple written output.",
                        "Recycle target language across units so learners revisit structures in new contexts.",
                    ],
                },
                "A2": {
                    "focus_strands": ["functional communication", "expanded reading", "connected speaking", "paragraph writing", "grammar for everyday meaning"],
                    "sequence_expectations": [
                        "Move from concrete daily-life communication toward description, comparison, explanation, and simple narration.",
                        "Strengthen reading fluency and listening stamina with age-appropriate topics and supported inference.",
                        "Use structured speaking and writing tasks to move students toward longer independent output.",
                    ],
                },
            },
            "lower_secondary": {
                "A1": {
                    "focus_strands": ["high-frequency adolescent vocabulary", "basic grammar in context", "short supported reading", "guided speaking", "sentence-to-short-paragraph writing"],
                    "sequence_expectations": [
                        "Use age-appropriate lower-secondary contexts such as school life, friendships, hobbies, routines, feelings, and technology instead of childish storylines.",
                        "Build from sentence-level understanding toward short connected texts, short dialogues, and scaffolded personal responses.",
                        "Recycle high-frequency language heavily so beginners at secondary age gain confidence without making the materials feel primary-level.",
                    ],
                },
                "A2": {
                    "focus_strands": ["communicative grammar", "reading inference", "interactive speaking", "paragraph-to-short-text writing", "strategic vocabulary growth"],
                    "sequence_expectations": [
                        "Consolidate core A2 communication while expanding text complexity and response depth.",
                        "Include regular speaking and listening tasks that require clarification, opinion, and reaction.",
                        "Use cumulative review to prevent grammar and vocabulary fragmentation.",
                    ],
                },
                "B1": {
                    "focus_strands": ["extended reading", "speaking for opinion and explanation", "multi-paragraph writing", "listening for detail and gist", "language accuracy"],
                    "sequence_expectations": [
                        "Move students from supported communication to more independent explanation, narration, and comparison.",
                        "Balance fluency with accuracy so grammar correction serves meaning, not isolated drills.",
                        "Introduce more authentic texts and real communicative tasks without losing scaffolding.",
                    ],
                },
                "B2": {
                    "focus_strands": ["extended interpretation", "discussion and justification", "multi-paragraph writing", "listening synthesis", "accuracy and register awareness"],
                    "sequence_expectations": [
                        "Extend B1 communication toward more independent interpretation, comparison, and supported debate while keeping topics adolescent-relevant.",
                        "Use longer texts and listening input, but keep scaffolding visible so advanced lower-secondary learners are stretched without being treated like adults.",
                        "Refine precision, cohesion, and register while keeping communication purposeful and meaningful.",
                    ],
                },
                "C1": {
                    "focus_strands": ["critical reading", "argumentation", "nuanced discussion", "extended analytical writing", "register control"],
                    "sequence_expectations": [
                        "Keep the intellectual demand high while ensuring the themes, examples, and tasks still feel appropriate for learners aged roughly 12 to 14.",
                        "Sequence advanced comprehension, discussion, and writing through structured modeling, text analysis, and supported independent response.",
                        "Use synthesis, evaluation, and interpretation tasks without defaulting to adult workplace or university-style contexts.",
                    ],
                },
                "C2": {
                    "focus_strands": ["near-native comprehension", "sustained argument", "text synthesis", "stylistic control", "independent interpretation"],
                    "sequence_expectations": [
                        "Maintain very high linguistic demand while keeping the curriculum anchored in age-appropriate lower-secondary topics, interests, and perspectives.",
                        "Balance sophisticated comprehension and expression with explicit guidance on structure, nuance, and evidence use.",
                        "Use advanced speaking, reading, and writing tasks that value precision and voice without drifting into adult-only domains.",
                    ],
                },
            },
            "upper_secondary": {
                "B1": {
                    "focus_strands": ["academic communication", "text interpretation", "discussion", "evidence-based writing", "exam readiness"],
                    "sequence_expectations": [
                        "Build from secure everyday communication toward more academic, analytical, and structured language use.",
                        "Use reading, writing, speaking, and listening tasks that prepare learners for independent study and assessments.",
                        "Spiral grammar and vocabulary through increasingly complex communicative demands.",
                    ],
                },
                "B2": {
                    "focus_strands": ["argumentation", "text synthesis", "presentation", "extended writing", "precision and register"],
                    "sequence_expectations": [
                        "Move from explanation to argument, evaluation, and sustained communication.",
                        "Build independence in reading and listening through longer texts, note-making, and synthesis.",
                        "Use structured debate, presentation, and essay work when pedagogically appropriate.",
                    ],
                },
            },
            "adult_stage": {
                "A1": {
                    "focus_strands": ["survival communication", "practical listening", "functional reading", "high-utility grammar", "confidence building"],
                    "sequence_expectations": [
                        "Prioritize immediate real-life language needs and confidence from day 1.",
                        "Use practical dialogs, forms, messages, and routine tasks before abstract content.",
                        "Balance speaking and listening with manageable reading and writing tasks.",
                    ],
                },
                "A2": {
                    "focus_strands": ["everyday autonomy", "transactional communication", "short text comprehension", "personal writing", "interaction strategies"],
                    "sequence_expectations": [
                        "Move from survival language to more independent social and practical communication.",
                        "Use role play and speaking tasks for travel, work, services, and community contexts.",
                        "Reinforce grammar through communicative reuse and correction that preserves confidence.",
                    ],
                },
                "B1": {
                    "focus_strands": ["independent communication", "work and study contexts", "extended reading", "discussion", "structured writing"],
                    "sequence_expectations": [
                        "Help adults explain opinions, narrate experiences, and manage practical extended interaction.",
                        "Integrate authentic adult contexts like work, study, administration, and social participation.",
                        "Combine fluency growth with targeted accuracy and strategy instruction.",
                    ],
                },
                "B2": {
                    "focus_strands": ["professional communication", "presentation", "critical reading", "argumentative writing", "nuance and register"],
                    "sequence_expectations": [
                        "Build toward confident independent communication in professional and academic situations.",
                        "Use debate, case discussion, and presentation tasks where appropriate.",
                        "Refine precision, tone, and extended discourse while keeping the sequence practical.",
                    ],
                },
            },
        },
    },
    "spanish": {
        "global_priorities": [
            "Treat Spanish as a full communicative curriculum with CEFR-style progression.",
            "Balance oral fluency, comprehension, literacy, and grammar in context.",
            "Recycle vocabulary and structures systematically across units.",
        ],
        "by_stage": {},
    },
    "mathematics": {
        "global_priorities": [
            "Respect conceptual prerequisites and avoid disconnected topic jumping.",
            "Balance fluency, reasoning, representation, and application.",
            "Use retrieval, worked examples, and cumulative review throughout the program.",
        ],
        "by_stage": {
            "early_primary": {
                "beginner_band": {
                    "focus_strands": ["number sense", "counting and place value beginnings", "comparison", "basic operations readiness", "mathematical language"],
                    "sequence_expectations": [
                        "Start with counting, quantity, patterns, and concrete manipulation.",
                        "Move from concrete models to pictorial representations before abstract symbols.",
                        "Use talk, sorting, movement, and visual supports to secure meaning.",
                    ],
                },
            },
            "upper_primary": {
                "beginner_band": {
                    "focus_strands": ["place value", "four operations", "fractions foundations", "measurement", "geometry basics", "word problems"],
                    "sequence_expectations": [
                        "Secure number sense and place value before expecting flexible calculation.",
                        "Introduce fractions conceptually, not only procedurally.",
                        "Use problem solving after conceptual understanding, not before it.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["fraction operations", "decimals and percentages", "multi-step problems", "geometry reasoning", "data handling"],
                    "sequence_expectations": [
                        "Move from secure arithmetic into connected proportional thinking and reasoning.",
                        "Interleave review of basic facts and procedures while introducing higher-demand problem solving.",
                        "Use representation changes to deepen conceptual understanding.",
                    ],
                },
            },
            "lower_secondary": {
                "beginner_band": {
                    "focus_strands": ["number fluency repair", "fractions and decimals", "ratio foundations", "introductory algebra language", "geometry basics"],
                    "sequence_expectations": [
                        "Repair insecure arithmetic and proportional foundations before expecting sustained abstract reasoning.",
                        "Use concrete, visual, verbal, and symbolic representations together so lower-secondary beginners can re-enter the curriculum with confidence.",
                        "Keep retrieval and confidence-building active while bridging toward the core secondary program.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["ratio and proportion", "algebra foundations", "geometry", "statistics", "reasoning and proof beginnings"],
                    "sequence_expectations": [
                        "Bridge arithmetic to algebra carefully through pattern, structure, and equivalence.",
                        "Use visual, verbal, and symbolic reasoning together.",
                        "Keep cumulative review active so foundational gaps do not block new learning.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["algebraic manipulation", "linear relationships", "geometric reasoning", "probability", "multi-step problem solving"],
                    "sequence_expectations": [
                        "Build abstract reasoning gradually from secure representations and prior understanding.",
                        "Sequence algebra as connected meaning, not symbol-only manipulation.",
                        "Use non-routine problems and justification tasks when students are ready.",
                    ],
                },
            },
            "upper_secondary": {
                "intermediate_band": {
                    "focus_strands": ["algebra consolidation", "functions", "geometry", "statistics", "exam fluency"],
                    "sequence_expectations": [
                        "Consolidate core secondary mathematics through spaced review and strategic application.",
                        "Move learners toward more independent selection of methods.",
                        "Use structured error analysis and mixed practice.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["advanced algebra", "functions and graphs", "proof and reasoning", "statistics and probability", "modeling"],
                    "sequence_expectations": [
                        "Build depth and abstraction through carefully sequenced representations and reasoning.",
                        "Move from procedure to justification, interpretation, and modeling.",
                        "Use cumulative synthesis tasks rather than isolated advanced topics.",
                    ],
                },
            },
            "adult_stage": {
                "beginner_band": {
                    "focus_strands": ["numeracy", "practical arithmetic", "financial math", "confidence rebuilding", "problem interpretation"],
                    "sequence_expectations": [
                        "Prioritize practical math confidence and success early.",
                        "Use real-life contexts to rebuild number sense and strategic reasoning.",
                        "Avoid overload and pace the program around meaningful application.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["algebra and numeracy", "functional problem solving", "data interpretation", "exam or work relevance", "strategy use"],
                    "sequence_expectations": [
                        "Blend practical application with concept repair and progression.",
                        "Use worked examples and verbal reasoning to strengthen independence.",
                        "Connect topics through authentic adult goals and needs.",
                    ],
                },
            },
        },
    },
    "science": {
        "global_priorities": [
            "Organize learning around concepts, phenomena, evidence, and explanation.",
            "Sequence vocabulary after experience and meaning, not before understanding.",
            "Blend practical inquiry with explicit concept building and review.",
        ],
        "by_stage": {
            "upper_primary": {
                "beginner_band": {
                    "focus_strands": ["living things", "materials", "forces and motion", "earth and space", "observation and classification"],
                    "sequence_expectations": [
                        "Begin with concrete observation, simple classification, and everyday phenomena.",
                        "Use prediction, noticing, describing, and simple explanation routines.",
                        "Keep practical inquiry tightly scaffolded and language-rich.",
                    ],
                },
            },
            "lower_secondary": {
                "beginner_band": {
                    "focus_strands": ["foundational scientific vocabulary", "observation and classification", "matter and forces basics", "cells and ecosystems foundations", "evidence talk"],
                    "sequence_expectations": [
                        "Start from concrete phenomena, shared observation, and clear scientific language before expecting formal explanation.",
                        "Move learners from noticing and describing toward short causal explanations and simple evidence use.",
                        "Revisit core lower-secondary science ideas repeatedly so vocabulary and concepts grow together.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["cells and systems", "matter", "energy", "forces", "ecosystems", "scientific method"],
                    "sequence_expectations": [
                        "Move from broad observable ideas to more formal scientific models and explanations.",
                        "Sequence practical work with concept clarification and evidence talk.",
                        "Revisit cross-cutting concepts such as system, change, cause, and evidence.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["scientific models", "quantitative reasoning", "data interpretation", "system thinking", "evidence-based explanation", "experimental design foundations"],
                    "sequence_expectations": [
                        "Extend core concepts into more abstract models, precise explanation, and stronger evidence use.",
                        "Integrate data interpretation, justification, and scientific reasoning rather than treating them as separate add-ons.",
                        "Use practical inquiry and analysis tasks that stretch advanced lower-secondary learners without skipping conceptual coherence.",
                    ],
                },
            },
            "upper_secondary": {
                "advanced_band": {
                    "focus_strands": ["disciplinary depth", "experimental design", "data interpretation", "scientific reasoning", "application and evaluation"],
                    "sequence_expectations": [
                        "Build toward precision, abstraction, and disciplined scientific explanation.",
                        "Use labs, simulations, data sets, and evidence-based writing where appropriate.",
                        "Sequence review and prerequisite repair carefully to support advanced content.",
                    ],
                },
            },
            "adult_stage": {
                "intermediate_band": {
                    "focus_strands": ["scientific literacy", "applied science contexts", "data reading", "concept explanation", "critical evaluation"],
                    "sequence_expectations": [
                        "Prioritize relevance, clarity, and confidence when building science understanding.",
                        "Connect scientific ideas to health, environment, technology, and daily life.",
                        "Use practical examples and discussion to support conceptual understanding.",
                    ],
                },
            },
        },
    },
    "music": {
        "global_priorities": [
            "Balance theory, listening, technique, performance, and creativity.",
            "Sequence from imitation to supported independence to confident performance.",
            "Use repetition and repertoire intelligently rather than as isolated drills.",
        ],
        "by_stage": {
            "early_primary": {
                "beginner_band": {
                    "focus_strands": ["pulse", "rhythm imitation", "pitch awareness", "listening", "musical confidence"],
                    "sequence_expectations": [
                        "Start with imitation, movement, call-and-response, and short listening tasks.",
                        "Keep notation light and tightly connected to sound and action.",
                        "Use repeated joyful rehearsal to build confidence and accuracy.",
                    ],
                },
            },
            "upper_primary": {
                "beginner_band": {
                    "focus_strands": ["rhythm reading", "melody", "notation basics", "ensemble habits", "performance routines"],
                    "sequence_expectations": [
                        "Move from musical play and imitation toward simple notation and short performances.",
                        "Balance practical music-making with tightly connected theory.",
                        "Revisit listening and repertoire in each unit rather than separating them.",
                    ],
                },
            },
            "lower_secondary": {
                "beginner_band": {
                    "focus_strands": ["pulse and rhythm security", "notation foundations", "listening recognition", "ensemble habits", "performance confidence"],
                    "sequence_expectations": [
                        "Consolidate basic musical literacy through hearing, doing, and short supported performances.",
                        "Keep notation tightly connected to sound, movement, and repertoire so the work feels musical rather than abstract.",
                        "Use short practice cycles and visible success points to build lower-secondary confidence and consistency.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["theory and notation", "aural skills", "performance technique", "interpretation", "musical vocabulary"],
                    "sequence_expectations": [
                        "Build more formal musical understanding while keeping performance central.",
                        "Use practice cycles that connect theory, hearing, and doing.",
                        "Include peer performance and reflective listening when useful.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["theory depth", "aural discrimination", "performance independence", "interpretation and style", "composition or improvisation"],
                    "sequence_expectations": [
                        "Move beyond basic literacy into more independent interpretation, stylistic awareness, and self-directed musical decision-making.",
                        "Connect theory to repertoire, listening, and performance so advanced work stays musical and authentic.",
                        "Use critique, reflection, and rehearsal cycles to strengthen both technique and expression.",
                    ],
                },
            },
            "adult_stage": {
                "beginner_band": {
                    "focus_strands": ["confidence", "technique foundations", "musical literacy", "repertoire", "listening and interpretation"],
                    "sequence_expectations": [
                        "Prioritize confidence and visible progress from the first unit.",
                        "Use practical repertoire to anchor theory and technical work.",
                        "Keep repetition purposeful and adult-relevant.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["technique development", "repertoire expansion", "theory integration", "performance confidence", "self-directed practice"],
                    "sequence_expectations": [
                        "Build independence in practice and interpretation gradually.",
                        "Sequence technique and repertoire so each supports the other.",
                        "Use performance and feedback checkpoints to create momentum.",
                    ],
                },
            },
        },
    },
    "study_skills": {
        "global_priorities": [
            "Teach routines, strategies, reflection, and transfer explicitly.",
            "Move from teacher-led structure toward student independence.",
            "Make every unit practical, visible, and immediately useful.",
        ],
        "by_stage": {
            "upper_primary": {
                "beginner_band": {
                    "focus_strands": ["organization", "attention", "routine building", "task completion", "reflection"],
                    "sequence_expectations": [
                        "Start with clear routines, materials management, and simple self-monitoring.",
                        "Teach one strategy at a time with heavy modeling and rehearsal.",
                        "Use checklists, habit loops, and small wins to build confidence.",
                    ],
                },
            },
            "lower_secondary": {
                "beginner_band": {
                    "focus_strands": ["organization", "task initiation", "note-taking basics", "homework routines", "teacher-guided reflection"],
                    "sequence_expectations": [
                        "Secure routines, organization, and visible structure before expecting independent strategy selection.",
                        "Teach one practical study habit at a time using real lower-secondary school tasks.",
                        "Use checklists, rehearsal, and quick reflection to build confidence and consistency.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["planning", "memory strategies", "revision", "time management", "metacognition"],
                    "sequence_expectations": [
                        "Build from external structure toward guided independence.",
                        "Teach revision and study strategies through real school tasks, not abstract advice.",
                        "Use reflection and transfer to help students generalize the routines.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["independent planning", "revision systems", "exam preparation", "strategy selection", "metacognitive evaluation"],
                    "sequence_expectations": [
                        "Move from guided routines toward self-chosen strategies that match task demands and deadlines.",
                        "Connect revision, planning, and focus routines directly to authentic lower-secondary assessment demands.",
                        "Use reflection on efficiency, transfer, and self-monitoring so students begin managing their own study systems.",
                    ],
                },
            },
            "upper_secondary": {
                "advanced_band": {
                    "focus_strands": ["independent planning", "exam preparation", "strategy selection", "focus management", "self-evaluation"],
                    "sequence_expectations": [
                        "Move learners toward self-directed planning, adaptation, and evaluation.",
                        "Link study skills directly to current academic demands and performance goals.",
                        "Use coached independence rather than constant teacher prompting.",
                    ],
                },
            },
            "adult_stage": {
                "intermediate_band": {
                    "focus_strands": ["routine design", "productivity", "memory and review", "goal setting", "self-regulation"],
                    "sequence_expectations": [
                        "Prioritize sustainable routines that fit adult schedules and responsibilities.",
                        "Use reflection, planning, and review cycles that learners can maintain independently.",
                        "Keep the program highly practical and transfer-focused.",
                    ],
                },
            },
        },
    },
    "general": {
        "global_priorities": [
            "Sequence from foundation to application with clear dependency logic.",
            "Keep the curriculum age-appropriate, coherent, and realistic for the stage and level selected.",
            "Use repeated review, retrieval, and transfer rather than isolated one-off topic coverage.",
        ],
        "by_stage": {
            "lower_secondary": {
                "beginner_band": {
                    "focus_strands": ["foundational knowledge", "key vocabulary", "structured practice", "confidence building", "guided review"],
                    "sequence_expectations": [
                        "Repair and secure the essentials before adding heavier abstraction or faster pacing.",
                        "Use clear routines, explicit modeling, and manageable lower-secondary contexts so students feel capable.",
                        "Build toward independent application gradually through repetition, examples, and short transfer tasks.",
                    ],
                },
                "intermediate_band": {
                    "focus_strands": ["topic understanding", "application", "communication", "retrieval", "growing independence"],
                    "sequence_expectations": [
                        "Move from secure understanding toward connected application and explanation.",
                        "Use age-appropriate lower-secondary examples, problems, or texts that feel purposeful rather than childish.",
                        "Blend review with new learning so the sequence stays coherent and cumulative.",
                    ],
                },
                "advanced_band": {
                    "focus_strands": ["analysis", "synthesis", "critique", "independent application", "transfer"],
                    "sequence_expectations": [
                        "Stretch learners with deeper reasoning and more independence while keeping the themes and tasks adolescent-appropriate.",
                        "Sequence complexity deliberately so advanced work still feels scaffolded and teachable.",
                        "Use richer discussion, interpretation, or problem-solving tasks that demand justification and reflection.",
                    ],
                },
            },
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_display_text(value: Any) -> str:
    text = _clean_text(value)
    if text:
        text = text[0].upper() + text[1:]
    return text


def _humanize_note_label(label: str) -> str:
    key = _clean_text(label).strip().lower()
    if not key:
        return ""
    translated = t(key)
    if translated != key:
        return translated
    return key.replace("_", " ").capitalize()


def _coerce_note_item(item: Any) -> list[str]:
    if isinstance(item, dict):
        out: list[str] = []
        for raw_key, raw_value in item.items():
            label = _humanize_note_label(str(raw_key))
            value = _clean_text(raw_value)
            if label and value:
                out.append(f"{label}: {value}")
            elif value:
                out.append(value)
        return out

    cleaned = _clean_text(item)
    if not cleaned:
        return []

    match = re.match(r"^\s*([a-z_]+)\s*:\s*(.+)$", cleaned, re.IGNORECASE)
    if match:
        label = _humanize_note_label(match.group(1))
        value = _clean_text(match.group(2))
        if label and value:
            return [f"{label}: {value}"]
        if value:
            return [value]

    return [cleaned]


def _ensure_list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_coerce_note_item(item))
        return out
    return _coerce_note_item(value)


def _ensure_int(value: Any, default: int, min_value: int = 0, max_value: int = 999) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _lines_to_list(value: str) -> list[str]:
    return [_clean_text(line) for line in str(value or "").splitlines() if _clean_text(line)]


def _normalize_subject_key(subject: str, custom_subject_name: str = "") -> tuple[str, str]:
    normalized = _lp().normalize_subject(subject)
    custom_name = _clean_display_text(custom_subject_name)
    if normalized == "other" and custom_name:
        return normalized, custom_name
    return normalized, ""


def _subject_display(subject_key: str, custom_subject_name: str = "") -> str:
    if str(subject_key or "").strip() == "other" and custom_subject_name:
        return _clean_display_text(custom_subject_name)
    return _lp().subject_label(subject_key)


def _subject_engine(subject_key: str) -> str:
    return _lp().get_subject_engine(subject_key)


def infer_subject_family(subject: str, custom_subject_name: str = "") -> str:
    normalized = _lp().normalize_subject(subject)
    engine = _subject_engine(normalized)
    if normalized != "other" and engine in _SUBJECT_GUIDANCE:
        return engine

    probe = f"{subject} {custom_subject_name}".strip().casefold()
    if not probe:
        return "general"

    best_family = "general"
    best_score = 0
    for family, keywords in _SUBJECT_FAMILY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in probe:
                score += max(1, len(keyword.split()))
        if score > best_score:
            best_score = score
            best_family = family
    return best_family


def get_subject_family(subject: str, custom_subject_name: str = "") -> str:
    return infer_subject_family(subject, custom_subject_name)


_STAGE_FALLBACK_SEQUENCE_START = {
    "early_primary": "Keep the sequence concrete, short-cycle, and highly scaffolded through routines, visuals, repetition, and immediate success.",
    "upper_primary": "Use clear structure, motivating school-age contexts, and guided independence so learners can explain and apply with confidence.",
    "lower_secondary": "Keep the tone respectful and adolescent-appropriate, with visible scaffolds that support more independent thinking and response.",
    "upper_secondary": "Use stronger academic demand, more independent application, and clearer justification while staying age-appropriate for teenagers.",
    "adult_stage": "Use practical, respectful, real-world contexts that connect directly to adult goals, confidence, and independent use.",
}

_LANGUAGE_FOCUS_BY_LEVEL = {
    "A1": ["high-frequency vocabulary", "listening comprehension", "guided speaking", "reading support", "sentence writing"],
    "A2": ["everyday vocabulary expansion", "short connected texts", "interactive speaking", "paragraph writing", "grammar in context"],
    "B1": ["extended reading", "speaking for opinion and explanation", "multi-paragraph writing", "listening for detail", "language accuracy"],
    "B2": ["extended interpretation", "discussion and justification", "multi-paragraph writing", "listening synthesis", "register awareness"],
    "C1": ["critical reading", "argumentation", "nuanced discussion", "analytical writing", "register control"],
    "C2": ["near-native comprehension", "sustained argument", "text synthesis", "stylistic control", "independent interpretation"],
}

_FAMILY_FOCUS_BY_BAND = {
    "math": {
        "beginner_band": ["foundational numeracy", "key representations", "guided calculation", "problem interpretation", "mathematical language"],
        "intermediate_band": ["core curriculum understanding", "method choice", "representation shifts", "problem solving", "explanation and reasoning"],
        "advanced_band": ["abstract reasoning", "multi-step problem solving", "justification", "modeling and transfer", "independent strategy use"],
    },
    "science": {
        "beginner_band": ["observation", "classification", "foundational scientific vocabulary", "simple cause and effect", "evidence talk"],
        "intermediate_band": ["concept understanding", "process explanation", "data interpretation", "investigation routines", "evidence-based reasoning"],
        "advanced_band": ["scientific models", "experimental design", "quantitative reasoning", "system thinking", "evaluation of evidence"],
    },
    "music": {
        "beginner_band": ["pulse and rhythm security", "notation foundations", "listening recognition", "performance confidence", "ensemble habits"],
        "intermediate_band": ["theory and notation", "aural skills", "performance technique", "interpretation", "musical vocabulary"],
        "advanced_band": ["advanced theory", "aural discrimination", "performance independence", "stylistic awareness", "composition or improvisation"],
    },
    "study_skills": {
        "beginner_band": ["organization", "task initiation", "routine building", "self-monitoring", "teacher-guided reflection"],
        "intermediate_band": ["planning", "memory strategies", "revision routines", "time management", "guided independence"],
        "advanced_band": ["independent planning", "revision systems", "strategy selection", "exam preparation", "metacognitive evaluation"],
    },
    "general": {
        "beginner_band": ["foundational knowledge", "key vocabulary", "structured practice", "guided comprehension", "confidence building"],
        "intermediate_band": ["topic understanding", "application", "communication", "retrieval", "growing independence"],
        "advanced_band": ["analysis", "synthesis", "critique", "transfer", "independent application"],
    },
}


def _fallback_focus_strands(subject: str, family: str, stage: str, level_or_band: str) -> list[str]:
    if family == "language":
        level = str(level_or_band or "").strip().upper()
        focus = list(_LANGUAGE_FOCUS_BY_LEVEL.get(level) or _LANGUAGE_FOCUS_BY_LEVEL["A2"])
        if stage == "early_primary" and level in {"A1", "A2"}:
            focus[0] = "phonological awareness"
            focus[3] = "early reading support"
        elif stage == "adult_stage" and level in {"A1", "A2"}:
            focus[0] = "survival and everyday vocabulary"
            focus[2] = "practical interaction"
        return focus

    band = str(level_or_band or "").strip().lower()
    family_focus = _FAMILY_FOCUS_BY_BAND.get(family) or _FAMILY_FOCUS_BY_BAND["general"]
    focus = list(family_focus.get(band) or family_focus.get("intermediate_band") or [])

    if family == "math" and stage == "early_primary" and band == "beginner_band":
        focus[0] = "counting and quantity"
    elif family == "math" and stage == "adult_stage" and band == "beginner_band":
        focus[0] = "practical numeracy"
    elif family == "science" and stage == "early_primary":
        focus[0] = "curiosity and observation"
    elif family == "study_skills" and stage == "adult_stage":
        focus[-1] = "self-regulation"
    elif family == "general" and stage == "adult_stage":
        focus[0] = "practical understanding"

    return focus


def _fallback_progression_line(family: str, level_or_band: str) -> str:
    level = str(level_or_band or "").strip()
    band = level.lower()

    if family == "language":
        if level == "A1":
            return "Start with highly supported comprehension and communication, then move toward short coherent texts, predictable interaction, and visible sentence building."
        if level == "A2":
            return "Move from secure everyday communication toward short connected texts, clearer opinion or reaction, and more independent paragraph-level output."
        if level in {"B1", "B2"}:
            return "Build from supported explanation toward interpretation, comparison, justification, and more sustained reading, listening, speaking, and writing."
        return "Keep the demand intellectually strong through interpretation, synthesis, nuance, and precision while staying appropriate to the learner stage."

    if family == "math":
        if band == "beginner_band":
            return "Repair prerequisites first, then bridge learners into the core curriculum through worked examples, structured rehearsal, and steadily increasing independence."
        if band == "intermediate_band":
            return "Move from secure understanding toward flexible method choice, explanation, and connected multi-step application."
        return "Stretch learners through richer reasoning, justification, and transfer, while keeping the build-up teachable and conceptually coherent."

    if family == "science":
        if band == "beginner_band":
            return "Begin with observable phenomena and simple explanation, then build scientific vocabulary, concept connections, and evidence-based responses."
        if band == "intermediate_band":
            return "Blend concept learning, investigation, evidence use, and explanation so students move from noticing to explaining and applying."
        return "Increase demand through modeling, data interpretation, evaluation of evidence, and more precise scientific reasoning."

    if family == "music":
        if band == "beginner_band":
            return "Build confidence through short repeated cycles that connect hearing, doing, and notation before expecting sustained independent performance."
        if band == "intermediate_band":
            return "Sequence theory, aural work, practice, and performance so the work feels musical, connected, and steadily more independent."
        return "Deepen interpretation, stylistic awareness, critique, and independent performance or composition without losing musical coherence."

    if family == "study_skills":
        if band == "beginner_band":
            return "Start with visible routines, teacher-guided strategy use, and repeated rehearsal before expecting independent study decisions."
        if band == "intermediate_band":
            return "Move from structured support toward guided independence in planning, revision, memory, and time management."
        return "Expect learners to compare, choose, adapt, and evaluate strategies for different tasks, deadlines, and performance goals."

    if band == "beginner_band":
        return "Secure foundations first, then build toward manageable independent application through repetition, examples, and clear success criteria."
    if band == "intermediate_band":
        return "Move from understanding toward purposeful application, communication, and retrieval in a coherent sequence."
    return "Stretch learners through deeper analysis, critique, and transfer while keeping the sequence practical and teachable."


def _fallback_review_line(subject: str, family: str, stage: str) -> str:
    if family == "language":
        return "Recycle high-value vocabulary, structures, and communicative routines across the sequence so fluency and accuracy grow together."
    if family == "math":
        return "Keep cumulative review active so gaps do not block new learning, and make reasoning visible through explanation and discussion."
    if family == "science":
        return "Revisit core ideas, vocabulary, and evidence routines across the sequence so scientific understanding grows cumulatively rather than as isolated facts."
    if family == "music":
        return "Use regular rehearsal, feedback, and reflection points so theory, listening, and performance keep reinforcing one another."
    if family == "study_skills":
        return "Anchor each strategy in real tasks and revisit it often enough that it becomes usable beyond a single lesson or unit."

    subject_text = _clean_text(subject).replace("_", " ")
    if subject_text and subject_text not in {"other", "general"}:
        return f"Keep the disciplinary habits of {subject_text} visible rather than collapsing the work into generic literacy tasks."
    if stage == "early_primary":
        return "Use repetition, modeling, and concrete examples so learners feel successful while building the right habits."
    return "Blend review with new learning so the sequence stays coherent, cumulative, and purposeful."


def _fallback_subject_specific_notes(subject: str, family: str, stage: str) -> list[str]:
    notes: list[str] = []
    normalized = _clean_text(subject).lower()
    if normalized == "spanish":
        notes.extend([
            "Prioritize pronunciation support, oral confidence, and meaningful communicative tasks in Spanish.",
            "Use age-appropriate cultural and communicative contexts relevant to Spanish learning.",
        ])
    elif family == "language" and stage in {"early_primary", "upper_primary"}:
        notes.append("Keep challenge age-appropriate by avoiding adult-style topics and preserving child-friendly contexts and supports.")
    elif family == "general" and normalized not in {"other", "general", ""}:
        notes.append(f"Keep the disciplinary logic of {normalized.replace('_', ' ')} visible in the tasks, examples, and outputs.")
    return notes


def _fallback_progression_level(subject: str, family: str, learner_stage: str, level_or_band: str) -> dict:
    return {
        "focus_strands": _fallback_focus_strands(subject, family, learner_stage, level_or_band),
        "sequence_expectations": [
            _STAGE_FALLBACK_SEQUENCE_START.get(
                str(learner_stage or "").strip(),
                _STAGE_FALLBACK_SEQUENCE_START["upper_primary"],
            ),
            _fallback_progression_line(family, level_or_band),
            _fallback_review_line(subject, family, learner_stage),
        ],
        "subject_specific_notes": _fallback_subject_specific_notes(subject, family, learner_stage),
    }


def _subject_progression_profile(subject: str, learner_stage: str, level_or_band: str, custom_subject_name: str = "") -> dict:
    normalized = _lp().normalize_subject(subject)
    family = infer_subject_family(subject, custom_subject_name)
    profile = _SUBJECT_PROGRESSION_PROFILES.get(normalized) or _SUBJECT_PROGRESSION_PROFILES.get(family) or {}
    global_priorities = profile.get("global_priorities") or []
    by_stage = profile.get("by_stage") or {}
    stage_profile = dict(by_stage.get(str(learner_stage or "").strip(), {}))

    level_key = str(level_or_band or "").strip()
    matched_level = stage_profile.get(level_key) if isinstance(stage_profile, dict) else None

    if normalized == "spanish" and not matched_level:
        english_profile = _SUBJECT_PROGRESSION_PROFILES.get("english") or {}
        english_stage_profile = (english_profile.get("by_stage") or {}).get(str(learner_stage or "").strip(), {})
        matched_level = dict(english_stage_profile.get(level_key) or {})
        if matched_level:
            return {
                "subject": normalized,
                "subject_family": family,
                "global_priorities": [
                    "Treat Spanish as a full communicative curriculum with CEFR-style progression.",
                    "Balance oral communication, comprehension, literacy, grammar, and vocabulary in context.",
                    "Use high-frequency Spanish structures and vocabulary in spiraled, meaningful reuse.",
                ],
                "focus_strands": matched_level.get("focus_strands") or [],
                "sequence_expectations": matched_level.get("sequence_expectations") or [],
                "subject_specific_notes": [
                    "Use age-appropriate cultural and communicative contexts relevant to Spanish learning.",
                    "Prioritize pronunciation support, oral confidence, and meaningful communicative tasks.",
                ],
            }

    if not matched_level:
        matched_level = _fallback_progression_level(subject, family, learner_stage, level_key)

    if not matched_level and isinstance(stage_profile, dict):
        if level_key in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            if level_key >= "B1":
                matched_level = stage_profile.get("B1") or stage_profile.get("B2") or next(iter(stage_profile.values()), {})
            else:
                matched_level = stage_profile.get("A1") or stage_profile.get("A2") or next(iter(stage_profile.values()), {})
        else:
            if "advanced" in level_key:
                matched_level = stage_profile.get("advanced_band") or stage_profile.get("intermediate_band") or next(iter(stage_profile.values()), {})
            elif "intermediate" in level_key:
                matched_level = stage_profile.get("intermediate_band") or stage_profile.get("beginner_band") or next(iter(stage_profile.values()), {})
            else:
                matched_level = stage_profile.get("beginner_band") or stage_profile.get("intermediate_band") or next(iter(stage_profile.values()), {})

    matched_level = matched_level or {}

    if normalized == "spanish" and not (_SUBJECT_PROGRESSION_PROFILES.get("spanish") or {}).get("by_stage"):
        return {
            "subject": normalized,
            "subject_family": family,
            "global_priorities": [
                "Treat Spanish as a full communicative curriculum with CEFR-style progression.",
                "Balance oral communication, comprehension, literacy, grammar, and vocabulary in context.",
                "Use high-frequency Spanish structures and vocabulary in spiraled, meaningful reuse.",
            ],
            "focus_strands": matched_level.get("focus_strands") or [],
            "sequence_expectations": matched_level.get("sequence_expectations") or [],
            "subject_specific_notes": [
                "Use age-appropriate cultural and communicative contexts relevant to Spanish learning.",
                "Prioritize pronunciation support, oral confidence, and meaningful communicative tasks.",
            ],
        }

    return {
        "subject": normalized,
        "subject_family": family,
        "global_priorities": global_priorities,
        "focus_strands": matched_level.get("focus_strands") or [],
        "sequence_expectations": matched_level.get("sequence_expectations") or [],
        "subject_specific_notes": matched_level.get("subject_specific_notes") or [],
    }


def get_subject_progression_profile(subject: str, learner_stage: str, level_or_band: str, custom_subject_name: str = "") -> dict:
    return _subject_progression_profile(subject, learner_stage, level_or_band, custom_subject_name)


def summarize_previous_program_context(previous_program: Optional[dict]) -> dict:
    if not previous_program:
        return {}

    units = previous_program.get("units") or []
    all_topic_titles: list[str] = []
    final_topics: list[str] = []
    for unit in units:
        unit_topics = [str(topic.get("title") or "").strip() for topic in (unit.get("topics") or []) if str(topic.get("title") or "").strip()]
        all_topic_titles.extend(unit_topics)
        if unit.get("unit_number") == len(units):
            final_topics.extend(unit_topics)

    return {
        "title": _clean_display_text(previous_program.get("title")),
        "subject": _clean_text(previous_program.get("subject")),
        "subject_display": _clean_text(previous_program.get("subject_display")),
        "learner_stage": _clean_text(previous_program.get("learner_stage")),
        "level_or_band": _clean_text(previous_program.get("level_or_band")),
        "entry_profile": _clean_text(previous_program.get("entry_profile")),
        "exit_profile": _clean_text(previous_program.get("exit_profile")),
        "scope_and_sequence_rationale": _clean_text(previous_program.get("scope_and_sequence_rationale")),
        "core_progression_priorities": _ensure_list_of_strings(previous_program.get("core_progression_priorities")),
        "best_practice_frameworks": _ensure_list_of_strings(previous_program.get("best_practice_frameworks")),
        "units_count": len(units),
        "topics_count": len(all_topic_titles),
        "topics_already_covered": all_topic_titles[:120],
        "final_topics": final_topics[:25],
        "teacher_rationale": _clean_text(previous_program.get("teacher_rationale")),
    }


def _structure_rule(subject: str, learner_stage: str) -> dict:
    stage_key = str(learner_stage or "").strip()
    engine = _subject_engine(subject)
    rule = dict(_STAGE_STRUCTURE_RULES.get(stage_key, _STAGE_STRUCTURE_RULES["upper_primary"]))
    override = _ENGINE_STRUCTURE_OVERRIDES.get(engine, {}).get(stage_key, {})
    rule.update(override)
    return rule


def recommend_program_structure(subject: str, learner_stage: str) -> dict:
    rule = _structure_rule(subject, learner_stage)
    return {
        "units_default": rule["units_default"],
        "units_min": rule["units_min"],
        "units_max": rule["units_max"],
        "lessons_per_unit_default": rule["lessons_default"],
        "lessons_per_unit_min": rule["lessons_min"],
        "lessons_per_unit_max": rule["lessons_max"],
        "total_topics_default": rule["units_default"] * rule["lessons_default"],
    }


def clamp_program_structure(
    subject: str,
    learner_stage: str,
    requested_units: Optional[int],
    requested_lessons_per_unit: Optional[int],
) -> dict:
    rule = recommend_program_structure(subject, learner_stage)
    units = _ensure_int(requested_units, rule["units_default"], rule["units_min"], rule["units_max"])
    lessons_per_unit = _ensure_int(
        requested_lessons_per_unit,
        rule["lessons_per_unit_default"],
        rule["lessons_per_unit_min"],
        rule["lessons_per_unit_max"],
    )

    notes: list[str] = []
    if requested_units is not None and units != int(requested_units):
        notes.append(
            t(
                "learning_program_units_adjusted",
                units=units,
                learner_stage=_lp()._stage_label(learner_stage),
            )
        )
    if requested_lessons_per_unit is not None and lessons_per_unit != int(requested_lessons_per_unit):
        notes.append(
            t(
                "learning_program_lessons_adjusted",
                lessons_per_unit=lessons_per_unit,
                learner_stage=_lp()._stage_label(learner_stage),
            )
        )

    return {
        "units": units,
        "lessons_per_unit": lessons_per_unit,
        "total_topics": units * lessons_per_unit,
        "notes": notes,
        "recommendation": rule,
    }


def _program_tagline(subject: str, learner_stage: str, level_or_band: str, custom_subject_name: str = "") -> str:
    subject_label = _subject_display(subject, custom_subject_name)
    stage_label = _lp()._stage_label(learner_stage)
    level_label = _lp()._level_label(level_or_band)
    return f"{subject_label} · {stage_label} · {level_label}"


def _best_practice_pack(subject: str) -> dict:
    engine = infer_subject_family(subject)
    return _SUBJECT_GUIDANCE.get(engine, _SUBJECT_GUIDANCE["general"])


def _recommended_lesson_purposes(subject: str) -> list[str]:
    purposes = list(_lp().LESSON_PURPOSES)
    engine = infer_subject_family(subject)
    if engine == "language":
        return purposes
    if engine == "study_skills":
        return [p for p in purposes if p != "discussion_exploration"] + ["discussion_exploration"]
    return purposes


def _recommended_worksheet_types(subject: str) -> list[str]:
    worksheet_types = list(_wb().WORKSHEET_TYPES)
    engine = infer_subject_family(subject)
    if engine == "math":
        preferred = ["short_answer", "matching", "multiple_choice", "true_false"]
        return [x for x in preferred if x in worksheet_types] + [x for x in worksheet_types if x not in preferred]
    if engine == "language":
        preferred = ["reading_comprehension", "fill_in_the_blanks", "matching", "multiple_choice", "short_answer"]
        return [x for x in preferred if x in worksheet_types] + [x for x in worksheet_types if x not in preferred]
    return worksheet_types


def _recommended_exam_exercises(subject: str) -> list[str]:
    available = list(_eb().EXAM_EXERCISE_TYPES)
    preferred = _eb().get_recommended_exercise_types(subject) if hasattr(_eb(), "get_recommended_exercise_types") else available[:]
    return [x for x in preferred if x in available] + [x for x in available if x not in preferred]


def _recommended_non_classio_activities(subject: str, custom_subject_name: str = "") -> list[str]:
    family = infer_subject_family(subject, custom_subject_name)
    return _NON_CLASSIO_ACTIVITY_BANK.get(family, _NON_CLASSIO_ACTIVITY_BANK["general"])


def _delivery_mode_guidance() -> dict:
    return dict(_DELIVERY_GUIDANCE)


def _level_sequence_order(level_or_band: str) -> int:
    level = str(level_or_band or "").strip()
    if level in _LANGUAGE_LEVEL_ORDER:
        return _LANGUAGE_LEVEL_ORDER.index(level) + 1
    if level in _ACADEMIC_LEVEL_ORDER:
        return _ACADEMIC_LEVEL_ORDER.index(level) + 1
    return 0


def _next_recommended_level(subject: str, learner_stage: str, current_level: str) -> str:
    level = str(current_level or "").strip()
    options = _lp().get_level_options(subject)
    if level in options:
        idx = options.index(level)
        if idx + 1 < len(options):
            return options[idx + 1]
    return _lp().recommend_default_level(subject, learner_stage)


def _make_sequence_group_id(subject: str, learner_stage: str, custom_subject_name: str = "") -> str:
    base = custom_subject_name if str(subject or "").strip() == "other" and custom_subject_name else subject
    return f"{_safe_slug(str(base))}-{_safe_slug(str(learner_stage))}-{uuid4().hex[:8]}"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _clean_text(value).casefold()).strip("-")
    return slug or "learning-program"


def _infer_subject_from_program_text(title: str, overview: str = "") -> str:
    haystack = f"{_clean_text(title)} {_clean_text(overview)}".casefold()
    for subject_key in _lp().QUICK_SUBJECTS:
        if subject_key == "other":
            continue
        aliases = {
            subject_key.casefold(),
            str(_lp().subject_label(subject_key) or "").casefold(),
        }
        if any(alias and alias in haystack for alias in aliases):
            return subject_key
    return ""


def _infer_level_from_program_text(title: str, overview: str = "") -> str:
    haystack = f"{_clean_text(title)} {_clean_text(overview)}"
    match = re.search(r"\b(A1|A2|B1|B2|C1|C2|beginner_band|intermediate_band|advanced_band)\b", haystack, re.IGNORECASE)
    return match.group(1) if match else ""


def _infer_stage_from_program_text(title: str, overview: str = "") -> str:
    haystack = f"{_clean_text(title)} {_clean_text(overview)}".casefold()
    hints = {
        "adult_stage": ["adult", "adults", "adult learners", "adultos", "yetişkin"],
        "upper_primary": ["upper primary", "primaria alta", "ilkokul üst"],
        "early_primary": ["early primary", "primaria inicial"],
        "lower_secondary": ["lower secondary", "secundaria baja"],
        "upper_secondary": ["upper secondary", "secundaria alta"],
    }
    for stage_key, aliases in hints.items():
        if any(alias in haystack for alias in aliases):
            return stage_key
    return ""


def _program_title(subject: str, learner_stage: str, level_or_band: str, custom_subject_name: str = "") -> str:
    subject_text = _subject_display(subject, custom_subject_name)
    stage_text = _lp()._stage_label(learner_stage)
    level_text = _lp()._level_label(level_or_band)
    return t("learning_program_title_format", subject=subject_text, stage=stage_text, level=level_text)


def _localized_worksheet_type_label(ws_type: str) -> str:
    translated = t(ws_type)
    if translated != ws_type:
        return translated
    return ws_type.replace("_", " ").title()


def _localized_exam_type_label(exercise_type: str) -> str:
    try:
        return _eb()._exercise_title(exercise_type)
    except Exception:
        translated = t(exercise_type)
        if translated != exercise_type:
            return translated
        return exercise_type.replace("_", " ").title()


def _localized_source_type_label(source_type: str) -> str:
    key = str(source_type or "").strip().lower()
    mapping = {
        "ai": t("mode_ai"),
        "template": t("template_fallback"),
        "custom": t("custom_label"),
        "classio": t("classio_label"),
    }
    return mapping.get(key, _clean_display_text(source_type))


def _classio_generation_notice_key(error_text: str) -> str:
    text = _clean_text(error_text).lower()
    if any(token in text for token in ("429", "quota", "resource_exhausted", "rate limit", "retry")):
        return "learning_program_notice_busy"
    if any(token in text for token in ("json", "valid json object", "delimiter")):
        return "learning_program_notice_shape"
    if any(token in text for token in ("sleeping", "unavailable", "helpers unavailable")):
        return "learning_program_notice_unavailable"
    return "learning_program_notice_general"


def _summarize_learning_program_fallback(errors: list[str] | None = None) -> str:
    notices: list[str] = []
    seen: set[str] = set()
    for error in errors or []:
        key = _classio_generation_notice_key(error)
        if key not in seen:
            notices.append(t(key))
            seen.add(key)
    return " ".join(notices).strip()


def _empty_program_shape() -> dict:
    return {
        "title": "",
        "program_overview": "",
        "teacher_rationale": "",
        "scope_and_sequence_rationale": "",
        "core_progression_priorities": [],
        "entry_profile": "",
        "exit_profile": "",
        "prerequisite_summary": "",
        "student_summary": "",
        "assessment_strategy": "",
        "resource_strategy": "",
        "subject_family": "",
        "delivery_design_notes": [],
        "non_classio_support_strategy": "",
        "best_practice_frameworks": [],
        "units": [],
    }


def _normalize_topic_record(topic: dict, fallback_topic_number: int, unit_number: int) -> dict:
    topic = topic or {}
    worksheet_types = [x for x in _ensure_list_of_strings(topic.get("suggested_worksheet_types")) if x in _wb().WORKSHEET_TYPES]
    exam_types = [x for x in _ensure_list_of_strings(topic.get("suggested_exam_exercise_types")) if x in _eb().EXAM_EXERCISE_TYPES]
    lesson_purpose = _clean_text(topic.get("lesson_purpose"))
    if lesson_purpose not in _lp().LESSON_PURPOSES:
        lesson_purpose = _lp().LESSON_PURPOSES[0]

    return {
        "topic_number": fallback_topic_number,
        "unit_number": unit_number,
        "title": _clean_display_text(topic.get("title") or topic.get("lesson_focus") or f"Topic {fallback_topic_number}"),
        "subtopic": _clean_display_text(topic.get("subtopic")),
        "lesson_focus": _clean_display_text(topic.get("lesson_focus") or topic.get("title")),
        "lesson_purpose": lesson_purpose,
        "learning_objectives": _ensure_list_of_strings(topic.get("learning_objectives")),
        "success_criteria": _ensure_list_of_strings(topic.get("success_criteria")),
        "student_can_do": _ensure_list_of_strings(topic.get("student_can_do")),
        "suggested_worksheet_types": worksheet_types,
        "suggested_exam_exercise_types": exam_types,
        "suggested_non_classio_activities": _ensure_list_of_strings(topic.get("suggested_non_classio_activities")),
        "delivery_notes": _ensure_list_of_strings(topic.get("delivery_notes")),
        "homework_idea": _clean_text(topic.get("homework_idea")),
        "teacher_notes": _clean_text(topic.get("teacher_notes")),
        "student_summary": _clean_text(topic.get("student_summary")),
        "estimated_lessons": _ensure_int(topic.get("estimated_lessons"), 1, 1, 6),
    }


def _normalize_unit_record(unit: dict, fallback_unit_number: int) -> dict:
    unit = unit or {}
    unit_number = _ensure_int(unit.get("unit_number"), fallback_unit_number, 1, 999)
    topics_in = unit.get("topics") if isinstance(unit.get("topics"), list) else []
    topics = [
        _normalize_topic_record(topic, idx + 1, unit_number)
        for idx, topic in enumerate(topics_in)
    ]

    lesson_purposes = [x for x in _ensure_list_of_strings(unit.get("recommended_lesson_purposes")) if x in _lp().LESSON_PURPOSES]
    worksheet_types = [x for x in _ensure_list_of_strings(unit.get("recommended_worksheet_types")) if x in _wb().WORKSHEET_TYPES]
    exam_types = [x for x in _ensure_list_of_strings(unit.get("recommended_exam_exercise_types")) if x in _eb().EXAM_EXERCISE_TYPES]

    return {
        "unit_number": unit_number,
        "title": _clean_display_text(unit.get("title") or f"Unit {unit_number}"),
        "overview": _clean_text(unit.get("overview")),
        "unit_objectives": _ensure_list_of_strings(unit.get("unit_objectives")),
        "recommended_lesson_purposes": lesson_purposes,
        "recommended_worksheet_types": worksheet_types,
        "recommended_exam_exercise_types": exam_types,
        "recommended_non_classio_activities": _ensure_list_of_strings(unit.get("recommended_non_classio_activities")),
        "delivery_notes": _ensure_list_of_strings(unit.get("delivery_notes")),
        "estimated_lessons": _ensure_int(unit.get("estimated_lessons"), max(1, len(topics)), 1, 24),
        "topics": topics,
    }


def normalize_learning_program_output(program: dict) -> dict:
    base = _empty_program_shape()
    src = dict(program or {})
    units_in = src.get("units") if isinstance(src.get("units"), list) else []
    units = [_normalize_unit_record(unit, idx + 1) for idx, unit in enumerate(units_in)]

    base.update(
        {
            "title": _clean_display_text(src.get("title")),
            "program_overview": _clean_text(src.get("program_overview")),
            "teacher_rationale": _clean_text(src.get("teacher_rationale")),
            "scope_and_sequence_rationale": _clean_text(src.get("scope_and_sequence_rationale")),
            "core_progression_priorities": _ensure_list_of_strings(src.get("core_progression_priorities")),
            "entry_profile": _clean_text(src.get("entry_profile")),
            "exit_profile": _clean_text(src.get("exit_profile")),
            "prerequisite_summary": _clean_text(src.get("prerequisite_summary")),
            "student_summary": _clean_text(src.get("student_summary")),
            "assessment_strategy": _clean_text(src.get("assessment_strategy")),
            "resource_strategy": _clean_text(src.get("resource_strategy")),
            "subject_family": _clean_text(src.get("subject_family")),
            "delivery_design_notes": _ensure_list_of_strings(src.get("delivery_design_notes")),
            "non_classio_support_strategy": _clean_text(src.get("non_classio_support_strategy")),
            "best_practice_frameworks": _ensure_list_of_strings(src.get("best_practice_frameworks")),
            "units": units,
        }
    )
    return base


def _fallback_program_payload(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    units: int,
    lessons_per_unit: int,
    custom_subject_name: str = "",
    previous_program: Optional[dict] = None,
) -> dict:
    subject_text = _subject_display(subject, custom_subject_name)
    stage_text = _lp()._stage_label(learner_stage)
    level_text = _lp()._level_label(level_or_band)
    pack = _best_practice_pack(subject)
    subject_family = infer_subject_family(subject, custom_subject_name)
    progression_profile = _subject_progression_profile(subject, learner_stage, level_or_band, custom_subject_name)
    lesson_purposes = _recommended_lesson_purposes(subject)
    worksheet_types = _recommended_worksheet_types(subject)
    exam_types = _recommended_exam_exercises(subject)
    non_classio_activities = _recommended_non_classio_activities(subject, custom_subject_name)
    previous_context = summarize_previous_program_context(previous_program) if previous_program else {}
    previous_exit_profile = _clean_text(previous_context.get("exit_profile"))
    previous_title = _clean_text(previous_context.get("title")) or t("learning_program_previous_program_fallback")
    prerequisite_summary = (
        previous_exit_profile
        or _clean_text(previous_context.get("scope_and_sequence_rationale"))
        or (
            t("learning_program_built_on_previous", title=previous_title)
            if previous_program
            else t("learning_program_default_prerequisite_summary")
        )
    )
    entry_profile = previous_exit_profile or t("learning_program_default_entry_profile")
    exit_profile = (
        t(
            "learning_program_progressive_exit_profile",
            subject=subject_text,
            level=level_text,
        )
        if previous_program
        else t("learning_program_default_exit_profile")
    )
    scope_rationale = (
        progression_profile["sequence_expectations"][0]
        if progression_profile.get("sequence_expectations")
        else t("learning_program_default_scope_sequence_rationale")
    )

    generated_units = []
    for unit_idx in range(1, units + 1):
        topics = []
        for topic_idx in range(1, lessons_per_unit + 1):
            purpose = lesson_purposes[(topic_idx - 1) % len(lesson_purposes)]
            topics.append(
                {
                    "topic_number": topic_idx,
                    "title": t("learning_program_fallback_topic_title", number=topic_idx),
                    "subtopic": "",
                    "lesson_focus": t("learning_program_fallback_topic_focus", subject=subject_text, number=topic_idx),
                    "lesson_purpose": purpose,
                    "learning_objectives": [
                        t("learning_program_fallback_topic_objective", unit=unit_idx, topic=topic_idx),
                    ],
                    "success_criteria": [
                        t("learning_program_fallback_success_criteria"),
                    ],
                    "student_can_do": [
                        t("learning_program_fallback_student_can_do"),
                    ],
                    "suggested_worksheet_types": worksheet_types[:3],
                    "suggested_exam_exercise_types": exam_types[:3],
                    "suggested_non_classio_activities": non_classio_activities[:2],
                    "delivery_notes": [t("learning_program_fallback_topic_delivery_note")],
                    "homework_idea": "",
                    "teacher_notes": progression_profile["sequence_expectations"][0] if progression_profile.get("sequence_expectations") else "",
                    "student_summary": "",
                    "estimated_lessons": 1,
                }
            )

        generated_units.append(
            {
                "unit_number": unit_idx,
                "title": t("learning_program_fallback_unit_title", number=unit_idx),
                "overview": t("learning_program_fallback_unit_overview", subject=subject_text, stage=stage_text, level=level_text),
                "unit_objectives": [
                    t("learning_program_fallback_unit_objective", unit=unit_idx),
                ],
                "recommended_lesson_purposes": lesson_purposes[:3],
                "recommended_worksheet_types": worksheet_types[:3],
                "recommended_exam_exercise_types": exam_types[:3],
                "recommended_non_classio_activities": non_classio_activities[:3],
                "delivery_notes": [t("learning_program_fallback_unit_delivery_note")],
                "estimated_lessons": lessons_per_unit,
                "topics": topics,
            }
        )

    return normalize_learning_program_output(
        {
            "title": _program_title(subject, learner_stage, level_or_band, custom_subject_name),
            "program_overview": t("learning_program_fallback_overview", subject=subject_text, stage=stage_text, level=level_text),
            "teacher_rationale": t("learning_program_default_teacher_rationale"),
            "scope_and_sequence_rationale": scope_rationale,
            "core_progression_priorities": progression_profile.get("focus_strands", [])[:5],
            "entry_profile": entry_profile,
            "exit_profile": exit_profile,
            "prerequisite_summary": prerequisite_summary,
            "student_summary": t("learning_program_default_student_summary", subject=subject_text),
            "assessment_strategy": t("learning_program_default_assessment_strategy"),
            "resource_strategy": t("learning_program_default_resource_strategy"),
            "subject_family": subject_family,
            "delivery_design_notes": [
                t("learning_program_default_delivery_note_one"),
                t("learning_program_default_delivery_note_two"),
            ],
            "non_classio_support_strategy": t("learning_program_default_non_classio_strategy"),
            "best_practice_frameworks": list(dict.fromkeys(pack["frameworks"] + progression_profile.get("global_priorities", [])[:2])),
            "units": generated_units,
        }
    )


def _build_program_generation_payload(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    units: int,
    lessons_per_unit: int,
    custom_subject_name: str = "",
    teaching_weeks: Optional[int] = None,
    additional_notes: str = "",
    previous_program: Optional[dict] = None,
) -> dict:
    guardrails = recommend_program_structure(subject, learner_stage)
    subject_family = infer_subject_family(subject, custom_subject_name)
    best_practice = _SUBJECT_GUIDANCE.get(subject_family, _SUBJECT_GUIDANCE["general"])
    progression_profile = _subject_progression_profile(subject, learner_stage, level_or_band, custom_subject_name)
    previous_context = summarize_previous_program_context(previous_program) if previous_program else {}
    return {
        "subject": subject,
        "subject_display": _subject_display(subject, custom_subject_name),
        "custom_subject_name": _clean_display_text(custom_subject_name),
        "subject_family": subject_family,
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "program_language": _lp().get_plan_language(),
        "student_material_language": _lp().get_student_material_language(subject),
        "requested_units": units,
        "requested_lessons_per_unit": lessons_per_unit,
        "teaching_weeks": _ensure_int(teaching_weeks, units * lessons_per_unit, 1, 104) if teaching_weeks else None,
        "recommended_lesson_purposes": _recommended_lesson_purposes(subject),
        "recommended_worksheet_types": _recommended_worksheet_types(subject),
        "recommended_exam_exercise_types": _recommended_exam_exercises(subject),
        "recommended_non_classio_activities": _recommended_non_classio_activities(subject, custom_subject_name),
        "classio_guardrails": guardrails,
        "best_practice_frameworks": best_practice["frameworks"],
        "best_practice_principles": best_practice["principles"],
        "subject_progression_profile": progression_profile,
        "delivery_mode_guidance": _delivery_mode_guidance(),
        "instructional_design_expectations": [
            "Act like a coordinated panel of PhD-level instructional designers, subject specialists, and learner-stage experts.",
            "Balance pedagogy, feasibility, motivation, and progression.",
            "Design for online, offline, and blended teaching realities.",
            "Keep Classio resources central, but do not force them where a better teacher-led or live activity is needed.",
            "If the subject is Other, infer the closest pedagogical family and adapt intelligently.",
            "For Classio-supported subjects, follow the subject progression profile closely so the scope and sequence feels production-ready.",
        ],
        "progression_chain_context": previous_context,
        "additional_notes": _clean_text(additional_notes),
        "required_output_shape": {
            "title": "string",
            "program_overview": "string",
            "teacher_rationale": "string",
            "scope_and_sequence_rationale": "string",
            "core_progression_priorities": ["string"],
            "entry_profile": "string",
            "exit_profile": "string",
            "prerequisite_summary": "string",
            "student_summary": "string",
            "assessment_strategy": "string",
            "resource_strategy": "string",
            "subject_family": "string",
            "delivery_design_notes": ["string"],
            "non_classio_support_strategy": "string",
            "best_practice_frameworks": ["string"],
            "units": [
                {
                    "unit_number": 1,
                    "title": "string",
                    "overview": "string",
                    "unit_objectives": ["string"],
                    "recommended_lesson_purposes": ["string"],
                    "recommended_worksheet_types": ["string"],
                    "recommended_exam_exercise_types": ["string"],
                    "recommended_non_classio_activities": ["string"],
                    "delivery_notes": ["string"],
                    "estimated_lessons": lessons_per_unit,
                    "topics": [
                        {
                            "topic_number": 1,
                            "title": "string",
                            "subtopic": "string",
                            "lesson_focus": "string",
                            "lesson_purpose": "string",
                            "learning_objectives": ["string"],
                            "success_criteria": ["string"],
                            "student_can_do": ["string"],
                            "suggested_worksheet_types": ["string"],
                            "suggested_exam_exercise_types": ["string"],
                            "suggested_non_classio_activities": ["string"],
                            "delivery_notes": ["string"],
                            "homework_idea": "string",
                            "teacher_notes": "string",
                            "student_summary": "string",
                            "estimated_lessons": 1,
                        }
                    ],
                }
            ],
        },
    }


def _build_program_skeleton_prompts(prompt_payload: dict) -> tuple[str, str]:
    system_prompt = (
        f"{build_expert_panel_prompt_blurb('learning_program')} "
        "You are Classio's senior curriculum architect. "
        "You reason like a PhD in instructional design, curriculum planning, and pedagogy. "
        "You understand online, offline, and blended teaching constraints globally. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "Build a teachable scope-and-sequence, not a random topic list. "
        "This is phase 1. Keep the response compact and structurally reliable. "
        "Teacher-facing text should use program_language. Student-facing summaries should be short and clear. "
        "Do not invent unsupported enum values for lesson purposes."
    )

    user_prompt = f"""
Create the compact skeleton of one complete learning program as JSON.

Builder input:
{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}

Rules:
- Return JSON only.
- Respect the requested unit count and lessons per unit exactly.
- The result must be sequenced and pedagogically coherent from day 1 onward.
- Follow the subject_progression_profile closely for supported Classio subjects.
- Use focus_strands and sequence_expectations to decide what belongs early, middle, and later in the program.
- If progression_chain_context is provided, build the new program as the next coherent step rather than starting from zero.
- Use progression_chain_context.exit_profile as the starting point for the new program's entry_profile.
- Do not unnecessarily repeat full previous-program coverage. Revisit only what is pedagogically important for bridging and retention.
- Make the new exit_profile clearly more advanced than the previous program.
- Avoid duplicate topic names across the program.
- Keep unit titles distinct and meaningful.
- Units should feel balanced, not overloaded.
- Sequence the curriculum like a real scope and sequence for the subject family and level.
- Respect age appropriateness, prerequisite knowledge, motivation, and realistic pacing.
- Keep each topic compact: title, subtopic, lesson_focus, lesson_purpose, and a short student_summary only.
- If subject is Other, infer the closest subject family and build the best-fit curriculum logic.
- lesson_purpose values must come from recommended_lesson_purposes.
- Each topic must be concrete enough to generate a lesson plan, worksheet, or exam later.
- Keep student_summary simple and motivating.

Required output shape:
{{
  "title": "string",
  "program_overview": "string",
  "teacher_rationale": "string",
  "scope_and_sequence_rationale": "string",
  "core_progression_priorities": ["string"],
  "entry_profile": "string",
  "exit_profile": "string",
  "prerequisite_summary": "string",
  "student_summary": "string",
  "assessment_strategy": "string",
  "resource_strategy": "string",
  "subject_family": "string",
  "delivery_design_notes": ["string"],
  "non_classio_support_strategy": "string",
  "best_practice_frameworks": ["string"],
  "units": [
    {{
      "unit_number": 1,
      "title": "string",
      "overview": "string",
      "topics": [
        {{
          "topic_number": 1,
          "title": "string",
          "subtopic": "string",
          "lesson_focus": "string",
          "lesson_purpose": "string",
          "student_summary": "string"
        }}
      ]
    }}
  ]
}}
"""
    return system_prompt, user_prompt


def _build_program_unit_enrichment_prompts(prompt_payload: dict, program_skeleton: dict, unit_skeleton: dict) -> tuple[str, str]:
    system_prompt = (
        f"{build_expert_panel_prompt_blurb('learning_program')} "
        "You are Classio's senior curriculum architect. "
        "You reason like a PhD in instructional design, curriculum planning, and pedagogy. "
        "You understand online, offline, and blended teaching constraints globally. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "This is phase 2. Enrich one unit only. "
        "Teacher-facing text should use program_language. Student-facing summaries should be short and clear. "
        "Use the provided enums exactly for lesson purposes, worksheet types, and exam exercise types."
    )

    unit_context = {
        "program_title": program_skeleton.get("title"),
        "program_overview": program_skeleton.get("program_overview"),
        "subject_family": program_skeleton.get("subject_family"),
        "entry_profile": program_skeleton.get("entry_profile"),
        "exit_profile": program_skeleton.get("exit_profile"),
        "core_progression_priorities": program_skeleton.get("core_progression_priorities"),
        "unit": unit_skeleton,
        "recommended_lesson_purposes": prompt_payload.get("recommended_lesson_purposes"),
        "recommended_worksheet_types": prompt_payload.get("recommended_worksheet_types"),
        "recommended_exam_exercise_types": prompt_payload.get("recommended_exam_exercise_types"),
        "recommended_non_classio_activities": prompt_payload.get("recommended_non_classio_activities"),
        "delivery_mode_guidance": prompt_payload.get("delivery_mode_guidance"),
        "subject_progression_profile": prompt_payload.get("subject_progression_profile"),
    }

    user_prompt = f"""
Enrich this single unit as JSON only.

Unit context:
{json.dumps(unit_context, ensure_ascii=False, indent=2)}

Rules:
- Return JSON only.
- Keep the existing unit title, overview, topic order, and topic titles coherent.
- Add unit_objectives, recommended resource types, recommended complementary activities, and delivery_notes.
- For each topic, add learning_objectives, success_criteria, student_can_do, suggested_worksheet_types, suggested_exam_exercise_types, suggested_non_classio_activities, delivery_notes, homework_idea, teacher_notes, student_summary, and estimated_lessons.
- Keep suggested_worksheet_types inside recommended_worksheet_types.
- Keep suggested_exam_exercise_types inside recommended_exam_exercise_types.
- Keep lesson_purpose values exactly as already defined in the unit skeleton.
- Use non-Classio activities only when they genuinely improve pedagogy.
- Respect online, offline, and blended feasibility.
- Keep each list concise and useful.

Required output shape:
{{
  "unit_number": 1,
  "title": "string",
  "overview": "string",
  "unit_objectives": ["string"],
  "recommended_lesson_purposes": ["string"],
  "recommended_worksheet_types": ["string"],
  "recommended_exam_exercise_types": ["string"],
  "recommended_non_classio_activities": ["string"],
  "delivery_notes": ["string"],
  "estimated_lessons": 4,
  "topics": [
    {{
      "topic_number": 1,
      "title": "string",
      "subtopic": "string",
      "lesson_focus": "string",
      "lesson_purpose": "string",
      "learning_objectives": ["string"],
      "success_criteria": ["string"],
      "student_can_do": ["string"],
      "suggested_worksheet_types": ["string"],
      "suggested_exam_exercise_types": ["string"],
      "suggested_non_classio_activities": ["string"],
      "delivery_notes": ["string"],
      "homework_idea": "string",
      "teacher_notes": "string",
      "student_summary": "string",
      "estimated_lessons": 1
    }}
  ]
}}
"""
    return system_prompt, user_prompt


def _summarize_prior_units(program: dict, current_unit_number: int) -> list[dict]:
    summaries: list[dict] = []
    for unit in program.get("units") or []:
        unit_number = int(unit.get("unit_number") or 0)
        if unit_number <= 0 or unit_number >= current_unit_number:
            continue
        summaries.append(
            {
                "unit_number": unit_number,
                "title": _clean_text(unit.get("title")),
                "overview": _clean_text(unit.get("overview")),
                "topics": [
                    {
                        "topic_number": int(topic.get("topic_number") or 0),
                        "title": _clean_text(topic.get("title")),
                        "lesson_focus": _clean_text(topic.get("lesson_focus")),
                        "student_summary": _clean_text(topic.get("student_summary")),
                    }
                    for topic in (unit.get("topics") or [])
                ],
            }
        )
    return summaries


def _program_has_generated_unit_details(unit: dict) -> bool:
    if unit.get("unit_objectives") or unit.get("delivery_notes") or unit.get("recommended_worksheet_types") or unit.get("recommended_exam_exercise_types"):
        return True
    for topic in unit.get("topics") or []:
        if topic.get("learning_objectives") or topic.get("success_criteria") or topic.get("suggested_worksheet_types") or topic.get("suggested_exam_exercise_types"):
            return True
    return False


def _call_learning_program_provider(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    generate_with_gemini,
    generate_with_openrouter,
    generate_with_openai,
) -> str:
    if provider == "gemini":
        return generate_with_gemini(system_prompt, user_prompt)
    if provider == "openrouter":
        return generate_with_openrouter(system_prompt, user_prompt)
    return generate_with_openai(system_prompt, user_prompt)


def _run_learning_program_json_generation(
    providers: list[str],
    system_prompt: str,
    user_prompt: str,
    extract_json_object_from_text,
    generate_with_gemini,
    generate_with_openrouter,
    generate_with_openai,
    log_ai_usage,
    meta: dict,
) -> tuple[dict, str, list[str]]:
    errors: list[str] = []
    for provider in providers:
        try:
            log_ai_usage(
                request_kind="learning_program_ai_stage",
                status="requested",
                meta={**meta, "provider": provider},
            )
            raw_text = _call_learning_program_provider(
                provider,
                system_prompt,
                user_prompt,
                generate_with_gemini,
                generate_with_openrouter,
                generate_with_openai,
            )
            parsed = extract_json_object_from_text(raw_text)
            log_ai_usage(
                request_kind="learning_program_ai_stage",
                status="success",
                meta={**meta, "provider": provider},
            )
            return parsed, provider, errors
        except Exception as e:
            errors.append(f"{provider}: {e}")
            try:
                log_ai_usage(
                    request_kind="learning_program_ai_stage",
                    status="failed",
                    meta={**meta, "provider": provider, "error": str(e)},
                )
            except Exception:
                pass
    raise ValueError(" | ".join(errors) if errors else "Unknown AI generation error")


def _merge_program_unit(base_unit: dict, enriched_unit: dict) -> dict:
    base_topics = list(base_unit.get("topics") or [])
    enriched_topics = list(enriched_unit.get("topics") or [])
    merged_topics = []
    target_count = max(len(base_topics), len(enriched_topics))

    for idx in range(target_count):
        merged = {}
        if idx < len(base_topics):
            merged.update(base_topics[idx] or {})
        if idx < len(enriched_topics):
            merged.update(enriched_topics[idx] or {})
        if not merged:
            continue
        merged["topic_number"] = idx + 1
        merged["unit_number"] = int(base_unit.get("unit_number") or enriched_unit.get("unit_number") or 1)
        merged_topics.append(merged)

    if len(base_topics) > len(merged_topics):
        for idx in range(len(merged_topics), len(base_topics)):
            topic = dict(base_topics[idx] or {})
            topic["topic_number"] = idx + 1
            topic["unit_number"] = int(base_unit.get("unit_number") or 1)
            merged_topics.append(topic)

    if not merged_topics:
        merged_topics = base_topics

    merged_unit = dict(base_unit)
    merged_unit.update(enriched_unit or {})
    merged_unit["topics"] = merged_topics
    return merged_unit


def _replace_program_unit(program: dict, updated_unit: dict) -> dict:
    program_copy = dict(program or {})
    units = []
    target_no = int(updated_unit.get("unit_number") or 0)
    for unit in program_copy.get("units") or []:
        unit_no = int(unit.get("unit_number") or 0)
        units.append(updated_unit if unit_no == target_no else unit)
    program_copy["units"] = units
    return program_copy


def generate_ai_learning_program_skeleton(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    requested_units: Optional[int] = None,
    requested_lessons_per_unit: Optional[int] = None,
    custom_subject_name: str = "",
    teaching_weeks: Optional[int] = None,
    additional_notes: str = "",
    previous_program: Optional[dict] = None,
) -> tuple[dict, str, Optional[str], dict]:
    structure = clamp_program_structure(subject, learner_stage, requested_units, requested_lessons_per_unit)
    fallback = _fallback_program_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=structure["units"],
        lessons_per_unit=structure["lessons_per_unit"],
        custom_subject_name=custom_subject_name,
        previous_program=previous_program,
    )
    payload = _build_program_generation_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=structure["units"],
        lessons_per_unit=structure["lessons_per_unit"],
        custom_subject_name=custom_subject_name,
        teaching_weeks=teaching_weeks,
        additional_notes=additional_notes,
        previous_program=previous_program,
    )

    try:
        from helpers.lesson_planner import (
            _extract_json_object_from_text,
            _generate_with_gemini,
            _generate_with_openai,
            _generate_with_openrouter,
            get_ai_provider_order,
        )
        from helpers.planner_storage import log_ai_usage
    except Exception:
        return fallback, "template", t("ai_unavailable_fallback"), payload

    skeleton_system_prompt, skeleton_user_prompt = _build_program_skeleton_prompts(payload)
    provider_order = get_ai_provider_order()

    try:
        log_ai_usage(
            request_kind="learning_program_ai",
            status="requested",
            meta={"subject": subject, "learner_stage": learner_stage, "level_or_band": level_or_band, "mode": "skeleton"},
        )
    except Exception:
        pass

    try:
        skeleton_raw, skeleton_provider, skeleton_errors = _run_learning_program_json_generation(
            providers=provider_order,
            system_prompt=skeleton_system_prompt,
            user_prompt=skeleton_user_prompt,
            extract_json_object_from_text=_extract_json_object_from_text,
            generate_with_gemini=_generate_with_gemini,
            generate_with_openrouter=_generate_with_openrouter,
            generate_with_openai=_generate_with_openai,
            log_ai_usage=log_ai_usage,
            meta={"subject": subject, "learner_stage": learner_stage, "level_or_band": level_or_band, "stage": "skeleton"},
        )
        parsed = normalize_learning_program_output(skeleton_raw)
        if not parsed.get("units"):
            raise ValueError("Program generation returned no units.")
        try:
            log_ai_usage(
                request_kind="learning_program_ai",
                status="success",
                meta={"subject": subject, "learner_stage": learner_stage, "level_or_band": level_or_band, "provider": skeleton_provider, "mode": "skeleton"},
            )
        except Exception:
            pass
        warning = t("ai_unavailable_fallback") if skeleton_errors else None
        return parsed, "ai", warning, payload
    except Exception as e:
        try:
            log_ai_usage(
                request_kind="learning_program_ai",
                status="failed",
                meta={"subject": subject, "learner_stage": learner_stage, "level_or_band": level_or_band, "error": str(e), "mode": "skeleton"},
            )
        except Exception:
            pass
        warning = t("ai_unavailable_fallback")
        return fallback, "template", warning, payload


def generate_ai_learning_program_unit(
    *,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    program: dict,
    unit_number: int,
    custom_subject_name: str = "",
    additional_notes: str = "",
    previous_program: Optional[dict] = None,
    payload: Optional[dict] = None,
) -> tuple[dict, str, Optional[str]]:
    program = normalize_learning_program_output(program)
    payload = payload or _build_program_generation_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=max(1, len(program.get("units") or [])),
        lessons_per_unit=max(1, max((len((unit.get("topics") or [])) for unit in (program.get("units") or [])), default=1)),
        custom_subject_name=custom_subject_name,
        additional_notes=additional_notes,
        previous_program=previous_program,
    )

    target_unit = None
    target_idx = -1
    for idx, unit in enumerate(program.get("units") or []):
        if int(unit.get("unit_number") or 0) == int(unit_number):
            target_unit = unit
            target_idx = idx
            break
    if not target_unit:
        return program, "template", t("learning_program_unit_not_found")

    fallback_units = (_fallback_program_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=max(1, len(program.get("units") or [])),
        lessons_per_unit=max(1, len(target_unit.get("topics") or [])),
        custom_subject_name=custom_subject_name,
        previous_program=previous_program,
    ).get("units") or [])
    fallback_unit = fallback_units[target_idx] if target_idx < len(fallback_units) else target_unit

    try:
        from helpers.lesson_planner import (
            _extract_json_object_from_text,
            _generate_with_gemini,
            _generate_with_openai,
            _generate_with_openrouter,
            get_ai_provider_order,
        )
        from helpers.planner_storage import log_ai_usage
    except Exception:
        merged = _merge_program_unit(target_unit, fallback_unit)
        updated = dict(program)
        updated["units"] = [merged if idx == target_idx else unit for idx, unit in enumerate(program.get("units") or [])]
        return updated, "template", t("ai_unavailable_fallback")

    unit_context = dict(target_unit)
    unit_context["prior_units_context"] = _summarize_prior_units(program, int(unit_number))
    if additional_notes:
        unit_context["additional_notes"] = additional_notes

    system_prompt, user_prompt = _build_program_unit_enrichment_prompts(payload, program, unit_context)
    provider_order = get_ai_provider_order()

    try:
        enriched_raw, provider, errors = _run_learning_program_json_generation(
            providers=provider_order,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            extract_json_object_from_text=_extract_json_object_from_text,
            generate_with_gemini=_generate_with_gemini,
            generate_with_openrouter=_generate_with_openrouter,
            generate_with_openai=_generate_with_openai,
            log_ai_usage=log_ai_usage,
            meta={"subject": subject, "learner_stage": learner_stage, "level_or_band": level_or_band, "stage": "unit_enrichment", "unit_number": int(unit_number)},
        )
        enriched_unit = _normalize_unit_record(enriched_raw, target_idx + 1)
        merged = _merge_program_unit(target_unit, enriched_unit)
        updated = dict(program)
        updated["units"] = [merged if idx == target_idx else unit for idx, unit in enumerate(program.get("units") or [])]
        warning = t("ai_unavailable_fallback") if errors else None
        return updated, provider, warning
    except Exception:
        merged = _merge_program_unit(target_unit, fallback_unit)
        updated = dict(program)
        updated["units"] = [merged if idx == target_idx else unit for idx, unit in enumerate(program.get("units") or [])]
        return updated, "template", t("ai_unavailable_fallback")


def generate_ai_learning_program(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    requested_units: Optional[int] = None,
    requested_lessons_per_unit: Optional[int] = None,
    custom_subject_name: str = "",
    teaching_weeks: Optional[int] = None,
    additional_notes: str = "",
    previous_program: Optional[dict] = None,
) -> tuple[dict, str, Optional[str]]:
    structure = clamp_program_structure(subject, learner_stage, requested_units, requested_lessons_per_unit)
    fallback = _fallback_program_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=structure["units"],
        lessons_per_unit=structure["lessons_per_unit"],
        custom_subject_name=custom_subject_name,
        previous_program=previous_program,
    )

    try:
        from helpers.lesson_planner import (
            _extract_json_object_from_text,
            _generate_with_gemini,
            _generate_with_openai,
            _generate_with_openrouter,
            get_ai_provider_order,
        )
        from helpers.planner_storage import get_ai_planner_usage_status, log_ai_usage
    except Exception:
        return fallback, "template", t("ai_unavailable_fallback")

    usage = get_ai_learning_program_usage_status()
    if AI_PROGRAM_LIMITS_ENABLED and usage["used_today"] >= AI_PROGRAM_DAILY_LIMIT:
        return fallback, "template", t("ai_limit_reached")

    if AI_PROGRAM_LIMITS_ENABLED and not usage["cooldown_ok"]:
        return fallback, "template", t("ai_cooldown_active", seconds=usage["seconds_left"])

    try:
        log_ai_usage(
            request_kind="learning_program_ai",
            status="requested",
            meta={
                "subject": subject,
                "learner_stage": learner_stage,
                "level_or_band": level_or_band,
            },
        )
    except Exception:
        pass

    payload = _build_program_generation_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        units=structure["units"],
        lessons_per_unit=structure["lessons_per_unit"],
        custom_subject_name=custom_subject_name,
        teaching_weeks=teaching_weeks,
        additional_notes=additional_notes,
        previous_program=previous_program,
    )
    skeleton_system_prompt, skeleton_user_prompt = _build_program_skeleton_prompts(payload)
    provider_order = get_ai_provider_order()

    try:
        skeleton_raw, skeleton_provider, skeleton_errors = _run_learning_program_json_generation(
            providers=provider_order,
            system_prompt=skeleton_system_prompt,
            user_prompt=skeleton_user_prompt,
            extract_json_object_from_text=_extract_json_object_from_text,
            generate_with_gemini=_generate_with_gemini,
            generate_with_openrouter=_generate_with_openrouter,
            generate_with_openai=_generate_with_openai,
            log_ai_usage=log_ai_usage,
            meta={
                "subject": subject,
                "learner_stage": learner_stage,
                "level_or_band": level_or_band,
                "stage": "skeleton",
            },
        )
        parsed = normalize_learning_program_output(skeleton_raw)
        if not parsed.get("units"):
            raise ValueError("Program generation returned no units.")
    except Exception as e:
        try:
            log_ai_usage(
                request_kind="learning_program_ai",
                status="failed",
                meta={
                    "subject": subject,
                    "learner_stage": learner_stage,
                    "level_or_band": level_or_band,
                    "error": str(e),
                },
            )
        except Exception:
            pass
        warning = t("ai_unavailable_fallback")
        return fallback, "template", warning

    provider_priority = [skeleton_provider] + [p for p in provider_order if p != skeleton_provider]
    partial_errors: list[str] = skeleton_errors
    merged_units: list[dict] = []
    fallback_units = fallback.get("units") or []

    for idx, unit in enumerate(parsed.get("units") or []):
        unit_system_prompt, unit_user_prompt = _build_program_unit_enrichment_prompts(payload, parsed, unit)
        try:
            enriched_raw, _, unit_errors = _run_learning_program_json_generation(
                providers=provider_priority,
                system_prompt=unit_system_prompt,
                user_prompt=unit_user_prompt,
                extract_json_object_from_text=_extract_json_object_from_text,
                generate_with_gemini=_generate_with_gemini,
                generate_with_openrouter=_generate_with_openrouter,
                generate_with_openai=_generate_with_openai,
                log_ai_usage=log_ai_usage,
                meta={
                    "subject": subject,
                    "learner_stage": learner_stage,
                    "level_or_band": level_or_band,
                    "stage": "unit_enrichment",
                    "unit_number": int(unit.get("unit_number") or idx + 1),
                },
            )
            partial_errors.extend(unit_errors)
            enriched_unit = _normalize_unit_record(enriched_raw, idx + 1)
            merged_units.append(_merge_program_unit(unit, enriched_unit))
        except Exception as e:
            partial_errors.append(f"{t('unit_label')} {idx + 1}: {e}")
            merged_units.append(fallback_units[idx] if idx < len(fallback_units) else unit)

    parsed["units"] = merged_units
    warning = t("ai_unavailable_fallback") if partial_errors else None
    try:
        log_ai_usage(
            request_kind="learning_program_ai",
            status="success",
            meta={
                "subject": subject,
                "learner_stage": learner_stage,
                "level_or_band": level_or_band,
                "provider": skeleton_provider,
                "partial_fallback": bool(partial_errors),
            },
        )
    except Exception:
        pass
    return parsed, "ai", warning


def get_ai_learning_program_usage_status() -> dict:
    try:
        from helpers.planner_storage import _safe_ai_logs_df
        from core.timezone import get_app_tz, today_local
        from datetime import datetime as _dt
    except Exception:
        return {
            "used_today": 0,
            "remaining_today": AI_PROGRAM_DAILY_LIMIT,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
            "limits_enabled": AI_PROGRAM_LIMITS_ENABLED,
        }

    df = _safe_ai_logs_df()
    now_utc = _dt.now(timezone.utc)
    today_start_utc = _dt.combine(today_local(), _dt.min.time()).replace(tzinfo=get_app_tz()).astimezone(timezone.utc)

    if df.empty:
        return {
            "used_today": 0,
            "remaining_today": AI_PROGRAM_DAILY_LIMIT,
            "cooldown_ok": True,
            "seconds_left": 0,
            "last_request_at": None,
            "limits_enabled": AI_PROGRAM_LIMITS_ENABLED,
        }

    program_df = df[(df["feature_name"] == "learning_program_ai") & (df["status"] == "success")].copy()
    today_df = program_df[(program_df["created_at"].notna()) & (program_df["created_at"] >= today_start_utc)].copy()
    used_today = int(len(today_df))

    cooldown_df = df[df["feature_name"] == "learning_program_ai"].dropna(subset=["created_at"]).sort_values("created_at")
    cooldown_ok = True
    seconds_left = 0
    last_request_at = None
    if not cooldown_df.empty:
        last_request_at = cooldown_df.iloc[-1]["created_at"]
        delta = (now_utc - last_request_at.to_pydatetime()).total_seconds()
        if delta < AI_PROGRAM_COOLDOWN_SECONDS:
            cooldown_ok = False
            seconds_left = int(max(0, math.ceil(AI_PROGRAM_COOLDOWN_SECONDS - delta)))

    return {
        "used_today": used_today,
        "remaining_today": max(0, AI_PROGRAM_DAILY_LIMIT - used_today),
        "cooldown_ok": cooldown_ok,
        "seconds_left": max(0, seconds_left),
        "last_request_at": last_request_at,
        "limits_enabled": AI_PROGRAM_LIMITS_ENABLED,
    }


def _count_program_topics(program: dict) -> int:
    count = 0
    for unit in program.get("units") or []:
        count += len(unit.get("topics") or [])
    return count


def _count_ready_program_units(program: dict) -> int:
    return sum(1 for unit in (program.get("units") or []) if _program_has_generated_unit_details(unit))


def _program_is_complete(program: dict) -> bool:
    units = program.get("units") or []
    if not units:
        return False
    return all(_program_has_generated_unit_details(unit) for unit in units)


def _flatten_program_rows(program: dict) -> tuple[list[dict], list[dict]]:
    units_payload: list[dict] = []
    topics_payload: list[dict] = []

    for unit in program.get("units") or []:
        units_payload.append(
            {
                "unit_number": unit["unit_number"],
                "title": unit["title"],
                "overview": unit["overview"],
                "unit_objectives": unit["unit_objectives"],
                "recommended_lesson_purposes": unit["recommended_lesson_purposes"],
                "recommended_worksheet_types": unit["recommended_worksheet_types"],
                "recommended_exam_exercise_types": unit["recommended_exam_exercise_types"],
                "estimated_lessons": unit["estimated_lessons"],
            }
        )
        for topic in unit.get("topics") or []:
            topics_payload.append(
                {
                    "unit_number": unit["unit_number"],
                    "topic_number": topic["topic_number"],
                    "title": topic["title"],
                    "subtopic": topic["subtopic"],
                    "lesson_focus": topic["lesson_focus"],
                    "lesson_purpose": topic["lesson_purpose"],
                    "learning_objectives": topic["learning_objectives"],
                    "success_criteria": topic["success_criteria"],
                    "student_can_do": topic["student_can_do"],
                    "suggested_worksheet_types": topic["suggested_worksheet_types"],
                    "suggested_exam_exercise_types": topic["suggested_exam_exercise_types"],
                    "homework_idea": topic["homework_idea"],
                    "teacher_notes": topic["teacher_notes"],
                    "student_summary": topic["student_summary"],
                    "estimated_lessons": topic["estimated_lessons"],
                }
            )

    return units_payload, topics_payload


def _program_record_payload(
    *,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    program: dict,
    visibility: str,
    source_type: str,
    custom_subject_name: str,
    status: str,
    generation_mode: str,
    program_language: Optional[str],
    student_material_language: Optional[str],
    builder_config: Optional[dict],
    parent_program_id: Optional[int],
    sequence_group_id: str,
    sequence_order: Optional[int],
    prerequisite_summary: str,
) -> tuple[dict, list[dict], list[dict]]:
    program = normalize_learning_program_output(program)
    subject_key, custom_name = _normalize_subject_key(subject, custom_subject_name)
    visibility = str(visibility or "private").strip().lower()
    if visibility not in PROGRAM_VISIBILITY_OPTIONS:
        visibility = "private"
    source_type = str(source_type or "ai").strip().lower()
    if source_type not in PROGRAM_SOURCE_TYPES:
        source_type = "ai"
    status = str(status or "draft").strip().lower()
    if status not in PROGRAM_STATUS_OPTIONS:
        status = "draft"

    is_complete = _program_is_complete(program)
    if not is_complete:
        visibility = "private"
        status = "draft"

    units_payload, topics_payload = _flatten_program_rows(program)
    total_units = len(units_payload)
    total_topics = len(topics_payload)

    payload = with_owner(
        {
            "title": program.get("title") or _program_title(subject_key, learner_stage, level_or_band, custom_name),
            "slug": _safe_slug(program.get("title") or _program_title(subject_key, learner_stage, level_or_band, custom_name)),
            "subject": subject_key,
            "custom_subject_name": custom_name or None,
            "learner_stage": _clean_text(learner_stage),
            "level_or_band": _clean_text(level_or_band),
            "program_language": program_language or _lp().get_plan_language(),
            "student_material_language": student_material_language or _lp().get_student_material_language(subject_key),
            "program_overview": program.get("program_overview", ""),
            "teacher_rationale": program.get("teacher_rationale", ""),
            "student_summary": program.get("student_summary", ""),
            "assessment_strategy": program.get("assessment_strategy", ""),
            "resource_strategy": program.get("resource_strategy", ""),
            "best_practice_frameworks": program.get("best_practice_frameworks", []),
            "source_type": source_type,
            "generation_mode": _clean_text(generation_mode or source_type),
            "visibility": visibility,
            "is_public": visibility == "public" and is_complete,
            "status": status,
            "total_units": total_units,
            "total_topics": total_topics,
            "builder_config": builder_config or {},
            "parent_program_id": int(parent_program_id) if parent_program_id else None,
            "sequence_group_id": _clean_text(sequence_group_id) or _make_sequence_group_id(subject_key, learner_stage, custom_name),
            "sequence_order": int(sequence_order) if sequence_order else _level_sequence_order(level_or_band),
            "prerequisite_summary": _clean_text(prerequisite_summary) or program.get("prerequisite_summary", ""),
            "entry_profile": program.get("entry_profile", ""),
            "exit_profile": program.get("exit_profile", ""),
            "program_data": program,
            "updated_at": _now_iso(),
        }
    )
    return payload, units_payload, topics_payload


def save_learning_program(
    *,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    program: dict,
    visibility: str = "private",
    source_type: str = "ai",
    custom_subject_name: str = "",
    status: str = "draft",
    generation_mode: str = "ai",
    program_language: Optional[str] = None,
    student_material_language: Optional[str] = None,
    builder_config: Optional[dict] = None,
    parent_program_id: Optional[int] = None,
    sequence_group_id: str = "",
    sequence_order: Optional[int] = None,
    prerequisite_summary: str = "",
) -> tuple[bool, Optional[int], str]:
    payload, units_payload, topics_payload = _program_record_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        program=program,
        visibility=visibility,
        source_type=source_type,
        custom_subject_name=custom_subject_name,
        status=status,
        generation_mode=generation_mode,
        program_language=program_language,
        student_material_language=student_material_language,
        builder_config=builder_config,
        parent_program_id=parent_program_id,
        sequence_group_id=sequence_group_id,
        sequence_order=sequence_order,
        prerequisite_summary=prerequisite_summary,
    )
    payload["created_at"] = _now_iso()

    try:
        sb = get_sb()
        inserted = sb.table("learning_programs").insert(payload).execute()
        rows = _rows(inserted)
        if not rows:
            return False, None, t("learning_program_save_failed_generic")
        program_id = int(rows[0]["id"])

        for unit in units_payload:
            unit_insert = (
                sb.table("learning_program_units")
                .insert(
                    {
                        "program_id": program_id,
                        **unit,
                        "created_at": _now_iso(),
                        "updated_at": _now_iso(),
                    }
                )
                .execute()
            )
            unit_rows = _rows(unit_insert)
            if not unit_rows:
                continue
            unit_id = int(unit_rows[0]["id"])
            unit_number = int(unit_rows[0]["unit_number"])
            unit_topics = [topic for topic in topics_payload if int(topic["unit_number"]) == unit_number]
            if unit_topics:
                sb.table("learning_program_topics").insert(
                    [
                        {
                            "program_id": program_id,
                            "unit_id": unit_id,
                            **topic,
                            "created_at": _now_iso(),
                            "updated_at": _now_iso(),
                        }
                        for topic in unit_topics
                    ]
                ).execute()

        clear_app_caches()
        return True, program_id, "saved"
    except Exception as e:
        return False, None, str(e)


def update_learning_program(
    *,
    program_id: int,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    program: dict,
    visibility: str = "private",
    source_type: str = "ai",
    custom_subject_name: str = "",
    status: str = "draft",
    generation_mode: str = "ai",
    program_language: Optional[str] = None,
    student_material_language: Optional[str] = None,
    builder_config: Optional[dict] = None,
    parent_program_id: Optional[int] = None,
    sequence_group_id: str = "",
    sequence_order: Optional[int] = None,
    prerequisite_summary: str = "",
) -> tuple[bool, str]:
    payload, units_payload, topics_payload = _program_record_payload(
        subject=subject,
        learner_stage=learner_stage,
        level_or_band=level_or_band,
        program=program,
        visibility=visibility,
        source_type=source_type,
        custom_subject_name=custom_subject_name,
        status=status,
        generation_mode=generation_mode,
        program_language=program_language,
        student_material_language=student_material_language,
        builder_config=builder_config,
        parent_program_id=parent_program_id,
        sequence_group_id=sequence_group_id,
        sequence_order=sequence_order,
        prerequisite_summary=prerequisite_summary,
    )

    uid = str(get_current_user_id() or "").strip()
    if not uid or int(program_id or 0) <= 0:
        return False, "missing_program"

    try:
        sb = get_sb()
        sb.table("learning_programs").update(payload).eq("id", int(program_id)).eq("user_id", uid).execute()

        existing_units = _rows(
            sb.table("learning_program_units")
            .select("id")
            .eq("program_id", int(program_id))
            .execute()
        )
        existing_unit_ids = [int(row.get("id") or 0) for row in existing_units if int(row.get("id") or 0) > 0]
        if existing_unit_ids:
            sb.table("learning_program_topics").delete().eq("program_id", int(program_id)).execute()
            sb.table("learning_program_units").delete().eq("program_id", int(program_id)).execute()

        for unit in units_payload:
            unit_insert = (
                sb.table("learning_program_units")
                .insert(
                    {
                        "program_id": int(program_id),
                        **unit,
                        "created_at": _now_iso(),
                        "updated_at": _now_iso(),
                    }
                )
                .execute()
            )
            unit_rows = _rows(unit_insert)
            if not unit_rows:
                continue
            unit_id = int(unit_rows[0]["id"])
            unit_number = int(unit_rows[0]["unit_number"])
            unit_topics = [topic for topic in topics_payload if int(topic["unit_number"]) == unit_number]
            if unit_topics:
                sb.table("learning_program_topics").insert(
                    [
                        {
                            "program_id": int(program_id),
                            "unit_id": unit_id,
                            **topic,
                            "created_at": _now_iso(),
                            "updated_at": _now_iso(),
                        }
                        for topic in unit_topics
                    ]
                ).execute()

        clear_app_caches()
        return True, "updated"
    except Exception as e:
        return False, str(e)


def load_my_learning_programs(
    limit: int = 500,
    *,
    include_archived: bool = False,
    archived_only: bool = False,
) -> pd.DataFrame:
    uid = get_current_user_id()
    if not uid:
        return pd.DataFrame()
    try:
        res = (
            get_sb()
            .table("learning_programs")
            .select("*")
            .eq("user_id", uid)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(_rows(res))
        if df.empty:
            return pd.DataFrame()
        for col in ("created_at", "updated_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return filter_archived_rows(
            df,
            include_archived=include_archived,
            archived_only=archived_only,
            default="active",
        )
    except Exception:
        return pd.DataFrame()


def load_public_learning_programs(limit: int = 500) -> pd.DataFrame:
    try:
        res = (
            get_sb()
            .table("learning_programs")
            .select("*")
            .eq("is_public", True)
            .neq("status", "archived")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(_rows(res))
        if df.empty:
            return pd.DataFrame()
        if "program_data" in df.columns:
            df = df[
                df["program_data"].apply(
                    lambda value: _program_is_complete(normalize_learning_program_output(value or {}))
                )
            ].copy()
        if df.empty:
            return pd.DataFrame()
        for col in ("created_at", "updated_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_progression_candidates(subject: str, learner_stage: str, custom_subject_name: str = "", limit: int = 200) -> pd.DataFrame:
    df = load_my_learning_programs(limit=limit)
    if df is None or df.empty:
        return pd.DataFrame()

    subject_key = _lp().normalize_subject(subject)
    out = df.copy()
    if "subject" in out.columns:
        out = out[out["subject"].astype(str).apply(_lp().normalize_subject) == subject_key]
    if subject_key == "other" and custom_subject_name and "custom_subject_name" in out.columns:
        out = out[out["custom_subject_name"].fillna("").astype(str).str.casefold() == _clean_text(custom_subject_name).casefold()]
    if "learner_stage" in out.columns:
        out = out[out["learner_stage"].astype(str) == str(learner_stage)]
    if "sequence_order" in out.columns:
        out["sequence_order"] = pd.to_numeric(out["sequence_order"], errors="coerce").fillna(0)
        out = out.sort_values(["sequence_order", "updated_at"], ascending=[False, False])
    elif "updated_at" in out.columns:
        out = out.sort_values("updated_at", ascending=False)
    return out.reset_index(drop=True)


def load_learning_program(program_id: int) -> dict:
    try:
        sb = get_sb()
        program_rows = _rows(sb.table("learning_programs").select("*").eq("id", int(program_id)).limit(1).execute())
        if not program_rows:
            return {}
        program_row = program_rows[0]

        unit_rows = _rows(
            sb.table("learning_program_units")
            .select("*")
            .eq("program_id", int(program_id))
            .order("unit_number")
            .execute()
        )
        topic_rows = _rows(
            sb.table("learning_program_topics")
            .select("*")
            .eq("program_id", int(program_id))
            .order("unit_number")
            .order("topic_number")
            .execute()
        )

        topics_by_unit: dict[int, list[dict]] = {}
        for topic in topic_rows:
            unit_id = int(topic.get("unit_id") or 0)
            unit_topics = topics_by_unit.setdefault(unit_id, [])
            unit_topics.append(
                {
                    "topic_number": len(unit_topics) + 1,
                    "unit_number": int(topic.get("unit_number") or 1),
                    "title": _clean_display_text(topic.get("title")),
                    "subtopic": _clean_display_text(topic.get("subtopic")),
                    "lesson_focus": _clean_display_text(topic.get("lesson_focus") or topic.get("title")),
                    "lesson_purpose": _clean_text(topic.get("lesson_purpose")),
                    "learning_objectives": topic.get("learning_objectives") or [],
                    "success_criteria": topic.get("success_criteria") or [],
                    "student_can_do": topic.get("student_can_do") or [],
                    "suggested_worksheet_types": topic.get("suggested_worksheet_types") or [],
                    "suggested_exam_exercise_types": topic.get("suggested_exam_exercise_types") or [],
                    "homework_idea": _clean_text(topic.get("homework_idea")),
                    "teacher_notes": _clean_text(topic.get("teacher_notes")),
                    "student_summary": _clean_text(topic.get("student_summary")),
                    "estimated_lessons": int(topic.get("estimated_lessons") or 1),
                    "topic_id": int(topic.get("id") or 0),
                }
            )

        units = []
        for unit in unit_rows:
            unit_id = int(unit.get("id") or 0)
            units.append(
                {
                    "unit_number": int(unit.get("unit_number") or 1),
                    "title": _clean_display_text(unit.get("title")),
                    "overview": _clean_text(unit.get("overview")),
                    "unit_objectives": unit.get("unit_objectives") or [],
                    "recommended_lesson_purposes": unit.get("recommended_lesson_purposes") or [],
                    "recommended_worksheet_types": unit.get("recommended_worksheet_types") or [],
                    "recommended_exam_exercise_types": unit.get("recommended_exam_exercise_types") or [],
                    "estimated_lessons": int(unit.get("estimated_lessons") or 1),
                    "unit_id": unit_id,
                    "topics": topics_by_unit.get(unit_id, []),
                }
            )

        return {
            **program_row,
            "subject_display": _subject_display(program_row.get("subject"), program_row.get("custom_subject_name")),
            "tagline": _program_tagline(
                program_row.get("subject"),
                program_row.get("learner_stage"),
                program_row.get("level_or_band"),
                program_row.get("custom_subject_name"),
            ),
            "units": units,
        }
    except Exception:
        return {}


def assign_learning_program(
    *,
    program_id: int,
    student_name: str,
    student_user_id: str = "",
    assigned_by_user_id: str = "",
    start_on: str = "",
    target_completion_on: str = "",
    note: str = "",
) -> tuple[bool, Optional[int], str]:
    teacher_id = get_current_user_id()
    if not teacher_id:
        return False, None, "missing_teacher"
    student_name = _clean_display_text(student_name)
    if not student_name:
        return False, None, "missing_student_name"
    student_user_id = _clean_text(student_user_id)
    if not student_user_id:
        return False, None, "assignment_link_required"

    linked_students = _tsi().load_active_linked_students_for_teacher()
    linked_student_ids = {str(row.get("student_id") or "").strip() for row in linked_students}
    if student_user_id not in linked_student_ids:
        return False, None, "assignment_link_required"

    payload = {
        "program_id": int(program_id),
        "teacher_id": teacher_id,
        "student_user_id": student_user_id or None,
        "student_name": student_name,
        "assigned_by_user_id": _clean_text(assigned_by_user_id) or teacher_id,
        "status": "assigned",
        "start_on": _clean_text(start_on) or None,
        "target_completion_on": _clean_text(target_completion_on) or None,
        "teacher_note": _clean_text(note),
        "assigned_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        res = get_sb().table("learning_program_assignments").insert(payload).execute()
        rows = _rows(res)
        if not rows:
            return False, None, "assign_failed"
        clear_app_caches()
        return True, int(rows[0]["id"]), "assigned"
    except Exception as e:
        return False, None, str(e)


def update_learning_program_visibility(program_id: int, visibility: str) -> tuple[bool, str]:
    visibility = str(visibility or "private").strip().lower()
    if visibility not in PROGRAM_VISIBILITY_OPTIONS:
        visibility = "private"
    program = load_learning_program(int(program_id))
    if visibility == "public" and not _program_is_complete(program):
        return False, "program_incomplete"
    try:
        get_sb().table("learning_programs").update(
            {
                "visibility": visibility,
                "is_public": visibility == "public" and _program_is_complete(program),
                "updated_at": _now_iso(),
            }
        ).eq("id", int(program_id)).eq("user_id", get_current_user_id()).execute()
        clear_app_caches()
        return True, "updated"
    except Exception as e:
        return False, str(e)


def update_learning_program_archive(program_id: int, archived: bool) -> tuple[bool, str]:
    uid = str(get_current_user_id() or "").strip()
    if not uid or int(program_id or 0) <= 0:
        return False, "missing_program"
    program = load_learning_program(int(program_id))
    if not program:
        return False, "missing_program"
    restored_status = "active" if _program_is_complete(program) else "draft"
    payload = {
        "status": ARCHIVED_STATUS if archived else restored_status,
        "visibility": "private",
        "is_public": False,
        "updated_at": _now_iso(),
    }
    try:
        (
            get_sb()
            .table("learning_programs")
            .update(payload)
            .eq("id", int(program_id))
            .eq("user_id", uid)
            .execute()
        )
        clear_app_caches()
        return True, "updated"
    except Exception as e:
        return False, str(e)


def archive_learning_program_assignment(assignment_id: int) -> tuple[bool, str]:
    teacher_id = str(get_current_user_id() or "").strip()
    if not teacher_id or not assignment_id:
        return False, "assign_failed"
    try:
        get_sb().table("learning_program_assignments").update(
            {
                "status": "archived",
                "updated_at": _now_iso(),
            }
        ).eq("id", int(assignment_id)).eq("teacher_id", teacher_id).execute()
        clear_app_caches()
        return True, "assignment_archived"
    except Exception as e:
        return False, str(e)


def load_program_assignments_for_teacher(limit: int = 500) -> pd.DataFrame:
    teacher_id = get_current_user_id()
    if not teacher_id:
        return pd.DataFrame()
    try:
        res = (
            get_sb()
            .table("learning_program_assignments")
            .select("*")
            .eq("teacher_id", teacher_id)
            .neq("status", "archived")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        df = pd.DataFrame(_rows(res))
        if df.empty:
            return pd.DataFrame()
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_program_assignments_for_student(student_user_id: str = "", student_name: str = "", limit: int = 500) -> pd.DataFrame:
    sb = get_sb()
    try:
        if student_user_id:
            res = (
                sb.table("learning_program_assignments")
                .select("*")
                .eq("student_user_id", _clean_text(student_user_id))
                .neq("status", "archived")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
        elif student_name:
            res = (
                sb.table("learning_program_assignments")
                .select("*")
                .ilike("student_name", _clean_text(student_name))
                .neq("status", "archived")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
        else:
            return pd.DataFrame()
        df = pd.DataFrame(_rows(res))
        if df.empty:
            return pd.DataFrame()
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def load_assignment_progress_map(assignment_id: int) -> dict[int, dict]:
    try:
        res = (
            get_sb()
            .table("learning_program_progress")
            .select("*")
            .eq("assignment_id", int(assignment_id))
            .execute()
        )
        rows = _rows(res)
        return {int(row.get("topic_id") or 0): row for row in rows}
    except Exception:
        return {}


def set_assignment_topic_progress(
    *,
    assignment_id: int,
    topic_id: int,
    done_by_teacher: Optional[bool] = None,
    done_by_student: Optional[bool] = None,
    note: str = "",
) -> bool:
    assignment_id = int(assignment_id)
    topic_id = int(topic_id)
    if assignment_id <= 0 or topic_id <= 0:
        return False

    try:
        sb = get_sb()
        existing_rows = _rows(
            sb.table("learning_program_progress")
            .select("*")
            .eq("assignment_id", assignment_id)
            .eq("topic_id", topic_id)
            .limit(1)
            .execute()
        )
        now = _now_iso()
        payload = {
            "assignment_id": assignment_id,
            "topic_id": topic_id,
            "teacher_done": bool(done_by_teacher) if done_by_teacher is not None else False,
            "student_done": bool(done_by_student) if done_by_student is not None else False,
            "note": _clean_text(note),
            "updated_at": now,
        }
        payload["is_done"] = bool(payload["teacher_done"] or payload["student_done"])
        if payload["is_done"]:
            payload["completed_at"] = now

        if existing_rows:
            current = existing_rows[0]
            if done_by_teacher is None:
                payload["teacher_done"] = bool(current.get("teacher_done"))
            if done_by_student is None:
                payload["student_done"] = bool(current.get("student_done"))
            payload["is_done"] = bool(payload["teacher_done"] or payload["student_done"])
            sb.table("learning_program_progress").update(payload).eq("id", int(current["id"])).execute()
        else:
            payload["created_at"] = now
            sb.table("learning_program_progress").insert(payload).execute()

        clear_app_caches()
        return True
    except Exception:
        return False


def render_learning_program_library_cards(
    df: pd.DataFrame,
    prefix: str = "learning_programs",
    show_author: bool = False,
    require_signup: bool = False,
    allow_visibility_toggle: bool = False,
    allow_archive_toggle: bool = False,
) -> None:
    if df is None or df.empty:
        st.info(t("no_learning_programs_found"))
        return

    profile_cache: dict[str, dict] = {}
    rows = df.reset_index(drop=True).to_dict("records")

    for idx in range(0, len(rows), 2):
        pair = rows[idx : idx + 2]
        cols = st.columns(2, gap="medium")

        for col_idx, row in enumerate(pair):
            with cols[col_idx]:
                row_program_raw = row.get("program_data") or {}
                row_program = normalize_learning_program_output(row_program_raw)
                row_title = _clean_text(row.get("title"))
                row_overview = _clean_text(row.get("program_overview"))
                row_subject = _clean_text(row.get("subject")) or _clean_text((row_program_raw or {}).get("subject")) or _infer_subject_from_program_text(row_title, row_overview)
                row_custom_subject = _clean_text(row.get("custom_subject_name")) or _clean_text((row_program_raw or {}).get("custom_subject_name"))
                row_stage = _clean_text(row.get("learner_stage")) or _clean_text((row_program_raw or {}).get("learner_stage")) or _infer_stage_from_program_text(row_title, row_overview)
                row_level = _clean_text(row.get("level_or_band")) or _clean_text((row_program_raw or {}).get("level_or_band")) or _infer_level_from_program_text(row_title, row_overview)
                title = _clean_display_text(row.get("title")) or t("untitled_learning_program")
                subject_text = _subject_display(row_subject, row_custom_subject)
                stage_text = _lp()._stage_label(row_stage) if row_stage else ""
                level_text = _lp()._level_label(row_level) if row_level else ""
                program_id = int(row.get("id") or 0)
                overview = _clean_text(row.get("program_overview"))
                total_units = int(row.get("total_units") or 0)
                total_topics = int(row.get("total_topics") or 0)
                visibility = t("public_label") if bool(row.get("is_public")) else t("private_label")
                is_archived = is_archived_status(row.get("status"))
                sequence_order = int(row.get("sequence_order") or 0)
                is_complete = _program_is_complete(row_program)
                if not total_units:
                    total_units = len(row_program.get("units") or [])
                if not total_topics:
                    total_topics = _count_program_topics(row_program)
                seq_label = f" · {t('path_step_label', step=sequence_order)}" if sequence_order > 0 else ""
                chips = "".join(
                    [
                        f'<span class="cm-resource-chip">📚 {html.escape(subject_text)}</span>' if subject_text else "",
                        f'<span class="cm-resource-chip">👥 {html.escape(stage_text)}</span>' if stage_text else "",
                        f'<span class="cm-resource-chip">🏷️ {html.escape(level_text)}</span>' if level_text else "",
                        f'<span class="cm-resource-chip">🪜 {html.escape(t("path_step_label", step=sequence_order))}</span>' if sequence_order > 0 else "",
                    ]
                )
                safe_title = html.escape(title)
                preview_text = html.escape((overview or t("no_description_available"))[:180])

                meta = ""
                meta += f'<div class="cm-resource-meta">📘 {html.escape(str(total_units) + " " + t("units").lower())}</div>'
                meta += f'<div class="cm-resource-meta">🧩 {html.escape(str(total_topics) + " " + t("topics_label").lower())}</div>'
                meta += f'<div class="cm-resource-meta">⚙️ {html.escape(visibility)}</div>'
                if is_archived:
                    meta += f'<div class="cm-resource-meta">🗂️ {html.escape(t("archived_label"))}</div>'
                if show_author:
                    author_id = _clean_text(row.get("user_id"))
                    if author_id:
                        if author_id not in profile_cache:
                            profile_cache[author_id] = load_profile_row(author_id)
                        profile = profile_cache.get(author_id) or {}
                        author_name = _clean_display_text(profile.get("display_name") or profile.get("username") or profile.get("email"))
                        if author_name:
                            meta += f'<div class="cm-resource-meta">👤 {html.escape(t("author_label_value", author=author_name))}</div>'
                if not is_complete:
                    meta += f'<div class="cm-resource-meta">⚠️ {html.escape(t("learning_program_incomplete_note"))}</div>'

                card_html = (
                    f'<div class="cm-resource-card cm-resource-program">'
                    f'<div class="cm-resource-card__title">{safe_title}</div>'
                    f'<div class="cm-resource-chip-row">{chips}</div>'
                    f'<div class="cm-resource-preview">{preview_text}</div>'
                    f'{meta}'
                    f'</div>'
                )

                st.markdown(card_html, unsafe_allow_html=True)

                is_owner = str(row.get("user_id") or "") == str(get_current_user_id() or "")
                show_owner_controls = allow_visibility_toggle or allow_archive_toggle
                action_cols = st.columns([1, 1, 1, 1] if show_owner_controls else [1, 1])
                with action_cols[0]:
                    if program_id > 0 and st.button(t("open_program"), key=f"{prefix}_open_{program_id}_{idx}_{col_idx}"):
                        st.session_state[f"{prefix}_selected_program_id"] = program_id
                with action_cols[1]:
                    if program_id > 0 and is_complete and not is_archived and st.button(t("assign_to_student"), key=f"{prefix}_assign_{program_id}_{idx}_{col_idx}"):
                        if require_signup:
                            st.session_state["_post_signup_open_panel"] = "files"
                            st.session_state["_post_signup_open_tab"] = "community_library"
                            st.session_state["_explore_go_signup"] = True
                            st.rerun()
                        st.session_state[f"{prefix}_selected_program_id"] = program_id
                        st.session_state[f"show_assign_learning_program_{program_id}"] = True
                if show_owner_controls:
                    with action_cols[2]:
                        if allow_visibility_toggle and is_owner and program_id > 0 and is_complete and not is_archived:
                            current_public = bool(row.get("is_public"))
                            new_public = st.toggle(
                                t("public_toggle_label"),
                                value=current_public,
                                key=f"{prefix}_toggle_visibility_{program_id}_{idx}_{col_idx}",
                            )
                            if new_public != current_public:
                                target_visibility = "public" if new_public else "private"
                                ok, msg = update_learning_program_visibility(program_id, target_visibility)
                                if ok:
                                    st.success(t("learning_program_visibility_updated", visibility=t("public_label") if target_visibility == "public" else t("private_label")))
                                    st.rerun()
                                if msg == "program_incomplete":
                                    st.error(t("learning_program_complete_before_publishing"))
                                else:
                                    st.error(t("learning_program_visibility_update_failed", error=msg))
                    with action_cols[3]:
                        if allow_archive_toggle and is_owner and program_id > 0:
                            new_archived = st.toggle(
                                t("archive_toggle_label"),
                                value=is_archived,
                                key=f"{prefix}_toggle_archive_{program_id}_{idx}_{col_idx}",
                            )
                            if new_archived != is_archived:
                                ok, msg = update_learning_program_archive(program_id, new_archived)
                                if ok:
                                    st.success(
                                        t(
                                            "resource_archive_updated",
                                            state=t("archived_label") if new_archived else t("restored_label"),
                                        )
                                    )
                                    st.rerun()
                                st.error(t("resource_archive_update_failed", error=msg))


def _inject_program_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-program-shell {
            position: relative;
            overflow: hidden;
            border-radius: 28px;
            padding: 1.25rem 1.35rem 1.1rem;
            background:
              radial-gradient(circle at top left, rgba(56,189,248,.18), transparent 32%),
              radial-gradient(circle at top right, rgba(34,197,94,.12), transparent 28%),
              linear-gradient(180deg, color-mix(in srgb, var(--panel) 86%, white 14%), var(--panel));
            border: 1px solid color-mix(in srgb, var(--border) 74%, rgba(56,189,248,.24) 26%);
            box-shadow: 0 20px 44px rgba(15,23,42,.10);
            margin-bottom: 1rem;
        }
        .classio-program-shell::after {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: linear-gradient(135deg, rgba(255,255,255,.08), transparent 35%);
        }
        .classio-program-kicker {
            font-size: .76rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .08em;
            color: #0f766e;
            margin-bottom: .55rem;
        }
        .classio-program-title {
            font-size: 1.42rem;
            line-height: 1.15;
            font-weight: 900;
            color: var(--text);
        }
        .classio-program-tagline {
            margin-top: .5rem;
            color: var(--muted);
            font-size: .96rem;
            font-weight: 600;
        }
        .classio-program-summary {
            margin-top: .9rem;
            color: var(--text);
            font-size: .98rem;
            line-height: 1.55;
        }
        .classio-program-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: .45rem;
            margin-top: .95rem;
        }
        .classio-program-chip {
            display: inline-flex;
            align-items: center;
            padding: .38rem .72rem;
            border-radius: 999px;
            background: rgba(255,255,255,.54);
            border: 1px solid rgba(148,163,184,.18);
            font-size: .78rem;
            font-weight: 800;
            color: var(--text);
        }
        .classio-program-unit {
            margin-top: .85rem;
            border-radius: 22px;
            padding: 1rem 1rem .85rem;
            background: rgba(255,255,255,.56);
            border: 1px solid rgba(148,163,184,.14);
            box-shadow: inset 0 1px 0 rgba(255,255,255,.4);
        }
        .classio-program-unit-title {
            font-size: 1.03rem;
            font-weight: 800;
            color: var(--text);
        }
        .classio-program-unit-copy {
            margin-top: .45rem;
            color: var(--muted);
            line-height: 1.5;
            font-size: .92rem;
        }
        .classio-student-program-card {
            position: relative;
            overflow: hidden;
            border-radius: 26px;
            padding: 1.15rem 1.15rem 1rem;
            background:
              radial-gradient(circle at top right, rgba(234,179,8,.18), transparent 30%),
              radial-gradient(circle at top left, rgba(59,130,246,.14), transparent 35%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 82%, white 18%));
            border: 1px solid color-mix(in srgb, var(--border) 76%, rgba(234,179,8,.18) 24%);
            box-shadow: 0 18px 38px rgba(15,23,42,.10);
            margin-bottom: 1rem;
        }
        .classio-student-program-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0,1fr));
            gap: .7rem;
            margin-top: .95rem;
        }
        .classio-student-program-stat {
            border-radius: 18px;
            padding: .85rem .9rem;
            background: rgba(255,255,255,.62);
            border: 1px solid rgba(148,163,184,.14);
        }
        .classio-student-program-stat-label {
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .06em;
            text-transform: uppercase;
            color: var(--muted);
        }
        .classio-student-program-stat-value {
            margin-top: .28rem;
            font-size: 1.16rem;
            font-weight: 900;
            color: var(--text);
        }
        .classio-program-topic {
            border-radius: 18px;
            padding: .9rem .95rem;
            background: rgba(255,255,255,.58);
            border: 1px solid rgba(148,163,184,.14);
            margin-top: .6rem;
        }
        .classio-program-topic-done {
            background:
              radial-gradient(circle at top right, rgba(16,185,129,.18), transparent 30%),
              linear-gradient(180deg, rgba(16,185,129,.10), rgba(45,212,191,.06));
            border-color: rgba(16,185,129,.24);
            box-shadow: 0 14px 24px rgba(16,185,129,.10);
        }
        .classio-program-topic-title {
            font-size: .97rem;
            font-weight: 800;
            color: var(--text);
        }
        .classio-program-topic-copy {
            margin-top: .25rem;
            color: var(--muted);
            font-size: .88rem;
            line-height: 1.45;
        }
        .classio-program-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 2rem;
            height: 2rem;
            border-radius: 999px;
            background: linear-gradient(135deg, #facc15, #f59e0b);
            color: #1f2937;
            font-size: .82rem;
            font-weight: 900;
            box-shadow: 0 10px 18px rgba(245,158,11,.22);
        }
        @media (max-width: 900px) {
            .classio-student-program-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_teacher_program_view(program: dict) -> None:
    if not program:
        st.info(t("no_program_selected"))
        return

    _inject_program_styles()
    parent_title = ""
    parent_id = int(program.get("parent_program_id") or 0)
    if parent_id > 0:
        parent_program = load_learning_program(parent_id)
        parent_title = _clean_text(parent_program.get("title"))

    st.markdown(
        f"""
        <div class="classio-program-shell">
            <div class="classio-program-kicker">{t("classio_learning_program")}</div>
            <div class="classio-program-title">{program.get('title') or t("learning_program_singular")}</div>
            <div class="classio-program-tagline">{program.get('tagline') or ''}</div>
            <div class="classio-program-summary">{program.get('program_overview') or ''}</div>
            <div class="classio-program-chip-row">
                <span class="classio-program-chip">{len(program.get('units') or [])} {t("units").lower()}</span>
                <span class="classio-program-chip">{_count_program_topics(program)} {t("topics_label").lower()}</span>
                <span class="classio-program-chip">{_localized_source_type_label(program.get('source_type') or 'custom')}</span>
                <span class="classio-program-chip">{t("public_label") if program.get('is_public') else t("private_label")}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    meta_cols = st.columns(4)
    meta_cols[0].metric(t("units"), len(program.get("units") or []))
    meta_cols[1].metric(t("topics_label"), _count_program_topics(program))
    meta_cols[2].metric(t("source_type"), _localized_source_type_label(program.get("source_type") or ""))
    meta_cols[3].metric(t("visibility_label"), t("public_label") if program.get("is_public") else t("private_label"))

    if parent_title:
        st.caption(t("learning_program_builds_on", title=parent_title))

    if program.get("teacher_rationale"):
        st.markdown(f"**{t('teacher_rationale_label')}**")
        st.write(program["teacher_rationale"])

    if program.get("scope_and_sequence_rationale"):
        st.markdown(f"**{t('scope_sequence_rationale_label')}**")
        st.write(program["scope_and_sequence_rationale"])

    if program.get("core_progression_priorities"):
        st.markdown(f"**{t('core_progression_priorities_label')}**")
        for item in program["core_progression_priorities"]:
            st.write(f"- {item}")

    if program.get("entry_profile"):
        st.markdown(f"**{t('entry_profile_label')}**")
        st.write(program["entry_profile"])

    if program.get("exit_profile"):
        st.markdown(f"**{t('exit_profile_label')}**")
        st.write(program["exit_profile"])

    if program.get("assessment_strategy"):
        st.markdown(f"**{t('assessment_strategy_label')}**")
        st.write(program["assessment_strategy"])

    if program.get("resource_strategy"):
        st.markdown(f"**{t('classio_resource_strategy_label')}**")
        st.write(program["resource_strategy"])

    if program.get("non_classio_support_strategy"):
        st.markdown(f"**{t('complementary_teaching_strategy_label')}**")
        st.write(program["non_classio_support_strategy"])

    if program.get("best_practice_frameworks"):
        st.caption(t("best_practice_anchors_label", items=", ".join(program["best_practice_frameworks"])))

    if program.get("subject_family"):
        st.caption(
            t(
                "inferred_subject_family_label",
                subject_family=_clean_display_text(program.get("subject_family")).replace("_", " "),
            )
        )

    if program.get("delivery_design_notes"):
        st.markdown(f"**{t('delivery_design_notes_label')}**")
        for item in program["delivery_design_notes"]:
            st.write(f"- {item}")

    for unit in program.get("units") or []:
        with st.expander(t("unit_title_format", number=unit.get("unit_number"), title=unit.get("title")), expanded=unit.get("unit_number") == 1):
            st.markdown(
                f"""
                <div class="classio-program-unit">
                    <div class="classio-program-unit-title">{t("unit_title_format", number=unit.get("unit_number"), title=unit.get("title"))}</div>
                    <div class="classio-program-unit-copy">{unit.get('overview') or ''}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if unit.get("unit_objectives"):
                st.markdown(f"**{t('unit_objectives_label')}**")
                for item in unit["unit_objectives"]:
                    st.write(f"- {item}")
            if unit.get("recommended_lesson_purposes"):
                st.caption(t("lesson_purposes_label", items=", ".join(_lp()._purpose_label(x) for x in unit["recommended_lesson_purposes"])))
            if unit.get("recommended_worksheet_types"):
                st.caption(t("worksheet_types_label", items=", ".join(_localized_worksheet_type_label(x) for x in unit["recommended_worksheet_types"])))
            if unit.get("recommended_exam_exercise_types"):
                st.caption(t("exam_exercise_types_label", items=", ".join(_localized_exam_type_label(x) for x in unit["recommended_exam_exercise_types"])))
            if unit.get("recommended_non_classio_activities"):
                st.caption(t("complementary_activities_label", items=", ".join(unit["recommended_non_classio_activities"])))
            if unit.get("delivery_notes"):
                for item in unit["delivery_notes"]:
                    st.write(f"- {item}")

            for topic in unit.get("topics") or []:
                with st.container(border=True):
                    st.markdown(f"**{t('topic_title_format', number=topic.get('topic_number'), title=topic.get('title'))}**")
                    if topic.get("subtopic"):
                        st.caption(topic["subtopic"])
                    if topic.get("student_summary"):
                        st.write(topic["student_summary"])
                    if topic.get("learning_objectives"):
                        st.write(t("objectives_label", items="; ".join(topic["learning_objectives"])))
                    if topic.get("success_criteria"):
                        st.write(t("success_criteria_label", items="; ".join(topic["success_criteria"])))
                    if topic.get("suggested_worksheet_types"):
                        st.caption(t("suggested_worksheet_types_label", items=", ".join(_localized_worksheet_type_label(x) for x in topic["suggested_worksheet_types"])))
                    if topic.get("suggested_exam_exercise_types"):
                        st.caption(t("suggested_exam_exercises_label", items=", ".join(_localized_exam_type_label(x) for x in topic["suggested_exam_exercise_types"])))
                    if topic.get("suggested_non_classio_activities"):
                        st.caption(t("complementary_activities_label", items=", ".join(topic["suggested_non_classio_activities"])))


def render_learning_program_assignment_panel(program: dict, prefix: str = "learning_program_assign") -> None:
    program_id = int(program.get("id") or 0)
    if program_id <= 0:
        st.info(t("save_program_before_assigning"))
        return

    st.markdown(f"### {t('assign_learning_program_title')}")

    linked_students = _tsi().load_active_linked_students_for_teacher()
    if not linked_students:
        st.info(t("assignment_requires_relationship_message"))
        return

    student_options = [row for row in linked_students if _clean_text(row.get("student_name"))]
    if not student_options:
        st.info(t("assignment_requires_relationship_message"))
        return

    labels = [_clean_text(row.get("student_name")) for row in student_options]
    selected_student_name = st.selectbox(
        t("student_name_label"),
        labels,
        key=f"{prefix}_student_name",
    )
    selected_row = next((row for row in student_options if _clean_text(row.get("student_name")) == selected_student_name), {})
    student_user_id = _clean_text(selected_row.get("student_id"))

    note = st.text_area(
        t("teacher_note"),
        key=f"{prefix}_teacher_note",
        placeholder=t("assignment_teacher_note_placeholder"),
    ).strip()

    if st.button(t("assign"), key=f"{prefix}_assign_btn"):
        ok, assignment_id, msg = assign_learning_program(
            program_id=program_id,
            student_name=selected_student_name,
            student_user_id=student_user_id,
            note=note,
        )
        if ok:
            st.success(t("learning_program_assigned_success", student=selected_student_name, assignment_id=assignment_id))
        else:
            st.error(t("learning_program_assigned_failed", error=msg))


def _save_generated_learning_program_from_builder(
    *,
    result: dict,
    meta: dict,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    custom_subject_name: str,
    visibility: str,
    mode_used: str,
) -> tuple[bool, Optional[int], str]:
    return save_learning_program(
        subject=meta.get("subject", subject),
        learner_stage=meta.get("learner_stage", learner_stage),
        level_or_band=meta.get("level_or_band", level_or_band),
        custom_subject_name=meta.get("custom_subject_name", custom_subject_name),
        visibility=meta.get("visibility", visibility),
        source_type="ai" if mode_used == "ai" else "custom",
        generation_mode=mode_used,
        builder_config=meta.get("builder_config") or {},
        status="draft",
        program=result,
        parent_program_id=meta.get("parent_program_id"),
        sequence_group_id=meta.get("sequence_group_id", ""),
        sequence_order=meta.get("sequence_order"),
        prerequisite_summary=meta.get("prerequisite_summary", ""),
    )


def render_learning_program_builder_preview(
    program: dict,
    ns: str,
    *,
    saved_program_id: Optional[int] = None,
    edit_meta: Optional[dict] = None,
) -> None:
    if not program:
        return

    _inject_program_styles()
    total_units = len(program.get("units") or [])
    total_topics = _count_program_topics(program)
    st.markdown(
        f"""
        <div class="classio-program-shell">
            <div class="classio-program-kicker">{t("classio_learning_program")}</div>
            <div class="classio-program-title">{program.get('title') or t("learning_program_singular")}</div>
            <div class="classio-program-tagline">{program.get('tagline') or ''}</div>
            <div class="classio-program-summary">{program.get('program_overview') or ''}</div>
            <div class="classio-program-chip-row">
                <span class="classio-program-chip">{total_units} {t("units").lower()}</span>
                <span class="classio-program-chip">{total_topics} {t("topics_label").lower()}</span>
                <span class="classio-program-chip">{_localized_source_type_label(program.get('source_type') or 'custom')}</span>
                <span class="classio-program-chip">{t("public_label") if program.get('is_public') else t("private_label")}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    complete_program = _program_is_complete(program)

    for idx, unit in enumerate(program.get("units") or []):
        unit_number = int(unit.get("unit_number") or idx + 1)
        generated = _program_has_generated_unit_details(unit)
        title_col, status_col, action_col = st.columns([5.4, 1.6, 1.6], vertical_alignment="center")
        with title_col:
            st.markdown(
                f"""
                <div class="classio-program-unit">
                    <div class="classio-program-unit-title">{t("unit_title_format", number=unit_number, title=unit.get("title"))}</div>
                    <div class="classio-program-unit-copy">{unit.get("overview") or ""}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with status_col:
            st.metric(
                t("builder_unit_status_label"),
                t("builder_unit_status_ready") if generated else t("builder_unit_status_skeleton"),
            )
        with action_col:
            if complete_program:
                if st.button(t("edit_unit"), key=f"{ns}_edit_unit_{unit_number}", use_container_width=True):
                    st.session_state[f"{ns}_editing_unit"] = unit_number
                    st.rerun()
            else:
                action_label = t("regenerate_unit_topics") if generated else t("generate_unit_topics")
                if st.button(action_label, key=f"{ns}_generate_unit_{unit_number}", use_container_width=True):
                    st.session_state[f"{ns}_pending_unit"] = unit_number
                    st.rerun()

        with st.expander(t("unit_title_format", number=unit_number, title=unit.get("title")), expanded=unit_number == 1):
            if unit.get("unit_objectives"):
                st.markdown(f"**{t('unit_objectives_label')}**")
                for item in unit["unit_objectives"]:
                    st.write(f"- {item}")
            if unit.get("recommended_lesson_purposes"):
                st.caption(t("lesson_purposes_label", items=", ".join(_lp()._purpose_label(x) for x in unit["recommended_lesson_purposes"])))
            elif unit.get("topics"):
                topic_purposes = [topic.get("lesson_purpose") for topic in unit.get("topics") or [] if topic.get("lesson_purpose")]
                if topic_purposes:
                    st.caption(t("lesson_purposes_label", items=", ".join(_lp()._purpose_label(x) for x in dict.fromkeys(topic_purposes))))
            if unit.get("recommended_worksheet_types"):
                st.caption(t("worksheet_types_label", items=", ".join(_localized_worksheet_type_label(x) for x in unit["recommended_worksheet_types"])))
            if unit.get("recommended_exam_exercise_types"):
                st.caption(t("exam_exercise_types_label", items=", ".join(_localized_exam_type_label(x) for x in unit["recommended_exam_exercise_types"])))
            if unit.get("recommended_non_classio_activities"):
                st.caption(t("complementary_activities_label", items=", ".join(unit["recommended_non_classio_activities"])))
            if unit.get("delivery_notes"):
                for item in unit["delivery_notes"]:
                    st.write(f"- {item}")

            for topic in unit.get("topics") or []:
                with st.container(border=True):
                    st.markdown(f"**{t('topic_title_format', number=topic.get('topic_number'), title=topic.get('title'))}**")
                    if topic.get("subtopic"):
                        st.caption(topic["subtopic"])
                    if topic.get("student_summary"):
                        st.write(topic["student_summary"])
                    if topic.get("learning_objectives"):
                        st.write(t("objectives_label", items="; ".join(topic["learning_objectives"])))
                    if topic.get("success_criteria"):
                        st.write(t("success_criteria_label", items="; ".join(topic["success_criteria"])))
                    if topic.get("suggested_worksheet_types"):
                        st.caption(t("suggested_worksheet_types_label", items=", ".join(_localized_worksheet_type_label(x) for x in topic["suggested_worksheet_types"])))
                    if topic.get("suggested_exam_exercise_types"):
                        st.caption(t("suggested_exam_exercises_label", items=", ".join(_localized_exam_type_label(x) for x in topic["suggested_exam_exercise_types"])))
                    if topic.get("suggested_non_classio_activities"):
                        st.caption(t("complementary_activities_label", items=", ".join(topic["suggested_non_classio_activities"])))

    editing_unit = st.session_state.get(f"{ns}_editing_unit")
    if complete_program and editing_unit:
        _render_learning_program_unit_editor(
            program=program,
            unit_number=int(editing_unit),
            ns=ns,
            saved_program_id=saved_program_id,
            saved_program_meta=edit_meta,
        )


def _render_learning_program_loading_shell(title: str, detail: str = "") -> None:
    _inject_program_styles()
    st.markdown(
        f"""
        <div class="classio-program-shell" style="margin-top:.65rem;">
            <div class="classio-program-kicker">{t("classio_learning_program")}</div>
            <div class="classio-program-title" style="font-size:1.08rem;">{title}</div>
            <div class="classio-program-summary">{detail}</div>
            <div class="classio-program-chip-row">
                <span class="classio-program-chip">Classio</span>
                <span class="classio-program-chip">{t("builder_unit_status_label")}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_learning_program_unit_editor(
    *,
    program: dict,
    unit_number: int,
    ns: str,
    saved_program_id: Optional[int] = None,
    saved_program_meta: Optional[dict] = None,
) -> None:
    units = program.get("units") or []
    target_unit = next((unit for unit in units if int(unit.get("unit_number") or 0) == int(unit_number)), None)
    if not target_unit:
        st.error(t("learning_program_unit_not_found"))
        return

    st.markdown(f"### {t('edit_unit_title', unit=unit_number)}")
    tabs = st.tabs([t("manual_edit_tab"), t("classio_ai_refine_tab")])

    with tabs[0]:
        title_key = f"{ns}_manual_title_{unit_number}"
        overview_key = f"{ns}_manual_overview_{unit_number}"
        objectives_key = f"{ns}_manual_objectives_{unit_number}"
        notes_key = f"{ns}_manual_notes_{unit_number}"

        st.text_input(t("unit_title_label"), value=target_unit.get("title") or "", key=title_key)
        st.text_area(t("overview_label"), value=target_unit.get("overview") or "", key=overview_key, height=100)
        st.text_area(
            t("unit_objectives_label"),
            value="\n".join(target_unit.get("unit_objectives") or []),
            key=objectives_key,
            height=120,
        )
        st.text_area(
            t("delivery_design_notes_label"),
            value="\n".join(target_unit.get("delivery_notes") or []),
            key=notes_key,
            height=120,
        )

        for topic_idx, topic in enumerate(target_unit.get("topics") or [], start=1):
            with st.expander(t("topic_title_format", number=topic_idx, title=topic.get("title")), expanded=topic_idx == 1):
                st.text_input(
                    t("topic_title_label"),
                    value=topic.get("title") or "",
                    key=f"{ns}_manual_topic_title_{unit_number}_{topic_idx}",
                )
                st.text_input(
                    t("subtopic_label"),
                    value=topic.get("subtopic") or "",
                    key=f"{ns}_manual_topic_subtopic_{unit_number}_{topic_idx}",
                )
                st.text_area(
                    t("student_summary_label"),
                    value=topic.get("student_summary") or "",
                    key=f"{ns}_manual_topic_summary_{unit_number}_{topic_idx}",
                    height=80,
                )

        save_label = t("save_unit_changes")
        if st.button(save_label, key=f"{ns}_manual_save_{unit_number}", use_container_width=True):
            updated_unit = dict(target_unit)
            updated_unit["title"] = _clean_display_text(st.session_state.get(title_key, ""))
            updated_unit["overview"] = _clean_text(st.session_state.get(overview_key, ""))
            updated_unit["unit_objectives"] = _lines_to_list(st.session_state.get(objectives_key, ""))
            updated_unit["delivery_notes"] = _lines_to_list(st.session_state.get(notes_key, ""))

            updated_topics = []
            for topic_idx, topic in enumerate(target_unit.get("topics") or [], start=1):
                updated_topic = dict(topic)
                updated_topic["title"] = _clean_display_text(st.session_state.get(f"{ns}_manual_topic_title_{unit_number}_{topic_idx}", ""))
                updated_topic["subtopic"] = _clean_display_text(st.session_state.get(f"{ns}_manual_topic_subtopic_{unit_number}_{topic_idx}", ""))
                updated_topic["student_summary"] = _clean_text(st.session_state.get(f"{ns}_manual_topic_summary_{unit_number}_{topic_idx}", ""))
                updated_topics.append(updated_topic)
            updated_unit["topics"] = updated_topics

            updated_program = _replace_program_unit(program, updated_unit)
            if saved_program_id and saved_program_meta:
                ok, msg = update_learning_program(
                    program_id=int(saved_program_id),
                    subject=saved_program_meta.get("subject"),
                    learner_stage=saved_program_meta.get("learner_stage"),
                    level_or_band=saved_program_meta.get("level_or_band"),
                    program=updated_program,
                    visibility=saved_program_meta.get("visibility") or "private",
                    source_type=saved_program_meta.get("source_type") or "ai",
                    custom_subject_name=saved_program_meta.get("custom_subject_name") or "",
                    status=saved_program_meta.get("status") or "draft",
                    generation_mode=saved_program_meta.get("generation_mode") or "ai",
                    program_language=saved_program_meta.get("program_language"),
                    student_material_language=saved_program_meta.get("student_material_language"),
                    builder_config=saved_program_meta.get("builder_config") or {},
                    parent_program_id=saved_program_meta.get("parent_program_id"),
                    sequence_group_id=saved_program_meta.get("sequence_group_id") or "",
                    sequence_order=saved_program_meta.get("sequence_order"),
                    prerequisite_summary=saved_program_meta.get("prerequisite_summary") or "",
                )
                if ok:
                    st.success(t("unit_changes_saved"))
                    st.session_state.pop(f"{ns}_editing_unit", None)
                    st.rerun()
                else:
                    st.error(t("learning_program_update_failed", error=msg))
            else:
                st.session_state[f"{ns}_result"] = updated_program
                st.success(t("unit_changes_saved"))
                st.session_state.pop(f"{ns}_editing_unit", None)
                st.rerun()

    with tabs[1]:
        prompt_key = f"{ns}_ai_refine_prompt_{unit_number}"
        st.text_area(
            t("unit_refine_prompt_label"),
            key=prompt_key,
            placeholder=t("unit_refine_prompt_placeholder"),
            height=120,
        )
        if st.button(t("refine_unit_with_classio"), key=f"{ns}_ai_refine_btn_{unit_number}", use_container_width=True):
            refine_prompt = _clean_text(st.session_state.get(prompt_key, ""))
            if not refine_prompt:
                st.error(t("unit_refine_prompt_required"))
            else:
                with st.status(t("building_learning_program_unit", unit=unit_number), expanded=True) as status:
                    status.write(t("learning_program_loading_previous_context"))
                    status.write(t("learning_program_loading_topic_map"))
                    status.write(t("learning_program_loading_teacher_student"))
                    updated_program, _mode_used, warning = generate_ai_learning_program_unit(
                        subject=(saved_program_meta or {}).get("subject", ""),
                        learner_stage=(saved_program_meta or {}).get("learner_stage", ""),
                        level_or_band=(saved_program_meta or {}).get("level_or_band", ""),
                        program=program,
                        unit_number=int(unit_number),
                        custom_subject_name=(saved_program_meta or {}).get("custom_subject_name", ""),
                        additional_notes=t("unit_refine_prompt_wrapped", prompt=refine_prompt),
                        previous_program=load_learning_program(int((saved_program_meta or {}).get("parent_program_id") or 0)) if int((saved_program_meta or {}).get("parent_program_id") or 0) > 0 else None,
                        payload=None,
                    )
                    status.update(label=t("learning_program_loading_ready"), state="complete")
                if saved_program_id and saved_program_meta:
                    ok, msg = update_learning_program(
                        program_id=int(saved_program_id),
                        subject=saved_program_meta.get("subject"),
                        learner_stage=saved_program_meta.get("learner_stage"),
                        level_or_band=saved_program_meta.get("level_or_band"),
                        program=updated_program,
                        visibility=saved_program_meta.get("visibility") or "private",
                        source_type=saved_program_meta.get("source_type") or "ai",
                        custom_subject_name=saved_program_meta.get("custom_subject_name") or "",
                        status=saved_program_meta.get("status") or "draft",
                        generation_mode=saved_program_meta.get("generation_mode") or "ai",
                        program_language=saved_program_meta.get("program_language"),
                        student_material_language=saved_program_meta.get("student_material_language"),
                        builder_config=saved_program_meta.get("builder_config") or {},
                        parent_program_id=saved_program_meta.get("parent_program_id"),
                        sequence_group_id=saved_program_meta.get("sequence_group_id") or "",
                        sequence_order=saved_program_meta.get("sequence_order"),
                        prerequisite_summary=saved_program_meta.get("prerequisite_summary") or "",
                    )
                    if ok:
                        if warning:
                            st.warning(warning)
                        st.success(t("unit_changes_saved"))
                        st.session_state.pop(f"{ns}_editing_unit", None)
                        st.rerun()
                    else:
                        st.error(t("learning_program_update_failed", error=msg))
                else:
                    st.session_state[f"{ns}_result"] = updated_program
                    if warning:
                        st.warning(warning)
                    st.success(t("unit_changes_saved"))
                    st.session_state.pop(f"{ns}_editing_unit", None)
                    st.rerun()

    if st.button(t("close_unit_editor"), key=f"{ns}_close_editor_{unit_number}", use_container_width=True):
        st.session_state.pop(f"{ns}_editing_unit", None)
        st.rerun()


def render_student_program_view(program: dict, assignment_id: Optional[int] = None, interactive: bool = False) -> None:
    if not program:
        st.info(t("no_program_selected"))
        return

    _inject_program_styles()
    progress_map = load_assignment_progress_map(int(assignment_id)) if assignment_id else {}

    total_topics = 0
    completed_topics = 0
    for unit in program.get("units") or []:
        for topic in unit.get("topics") or []:
            total_topics += 1
            topic_progress = progress_map.get(int(topic.get("topic_id") or 0), {})
            if topic_progress.get("is_done"):
                completed_topics += 1

    progress_ratio = (completed_topics / total_topics) if total_topics else 0.0
    streak_label = t("student_program_on_a_roll") if completed_topics and completed_topics < total_topics else (t("student_program_complete") if total_topics and completed_topics == total_topics else t("student_program_ready_to_begin"))
    points = completed_topics * 25
    badge = t("student_program_badge_starter")
    if completed_topics >= 5:
        badge = t("student_program_badge_momentum")
    if completed_topics >= 12:
        badge = t("student_program_badge_consistency")
    if total_topics and completed_topics == total_topics:
        badge = t("student_program_badge_finisher")

    st.markdown(
        f"""
        <div class="classio-student-program-card">
            <div class="classio-program-kicker">{t("assigned_learning_program")}</div>
            <div class="classio-program-title">{program.get('title') or t("learning_program_singular")}</div>
            <div class="classio-program-tagline">{program.get('student_summary') or program.get('tagline') or ''}</div>
            <div class="classio-student-program-grid">
                <div class="classio-student-program-stat">
                    <div class="classio-student-program-stat-label">{t("progress_label")}</div>
                    <div class="classio-student-program-stat-value">{completed_topics}/{total_topics}</div>
                </div>
                <div class="classio-student-program-stat">
                    <div class="classio-student-program-stat-label">{t("points_label")}</div>
                    <div class="classio-student-program-stat-value">{points}</div>
                </div>
                <div class="classio-student-program-stat">
                    <div class="classio-student-program-stat-label">{t("badge_label")}</div>
                    <div class="classio-student-program-stat-value">{badge}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(progress_ratio, text=t("student_program_progress_text", completed=completed_topics, total=total_topics, streak_label=streak_label))

    global_topic_number = 0
    for unit in program.get("units") or []:
        with st.expander(t("unit_title_format", number=unit.get("unit_number"), title=unit.get("title")), expanded=unit.get("unit_number") == 1):
            for topic in unit.get("topics") or []:
                global_topic_number += 1
                topic_id = int(topic.get("topic_id") or 0)
                topic_progress = progress_map.get(topic_id, {})
                done = bool(topic_progress.get("is_done"))
                cols = st.columns([0.12, 0.88])
                with cols[0]:
                    if interactive and assignment_id and topic_id > 0:
                        new_done = st.checkbox(
                            t("done_label"),
                            value=done,
                            key=f"learning_program_done_{assignment_id}_{topic_id}",
                            label_visibility="collapsed",
                        )
                        if new_done != done:
                            set_assignment_topic_progress(
                                assignment_id=int(assignment_id),
                                topic_id=topic_id,
                                done_by_student=new_done,
                            )
                            st.rerun()
                    else:
                        st.write("✅" if done else "⬜")
                with cols[1]:
                    st.markdown(
                        f"""
                        <div class="classio-program-topic {'classio-program-topic-done' if done else ''}">
                            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.8rem;">
                                <div>
                                    <div class="classio-program-topic-title">{t("topic_title_format", number=global_topic_number, title=topic.get("title"))}</div>
                                    <div class="classio-program-topic-copy">{topic.get('student_summary') or topic.get('lesson_focus') or topic.get('subtopic') or ''}</div>
                                </div>
                                <div class="classio-program-badge">{'+' + str(25) if done else str(global_topic_number)}</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    summary = topic.get("student_summary") or topic.get("lesson_focus") or topic.get("subtopic")
                    extra_bits = []
                    if topic.get("lesson_purpose"):
                        extra_bits.append(_clean_display_text(topic.get("lesson_purpose")).replace("_", " "))
                    if topic.get("suggested_worksheet_types"):
                        extra_bits.append(t("practice_label", items=", ".join(_localized_worksheet_type_label(x) for x in topic.get("suggested_worksheet_types")[:2])))
                    if summary and not extra_bits:
                        st.caption(summary)
                    elif extra_bits:
                        st.caption(" · ".join(extra_bits))


def render_saved_learning_program_workspace(program: dict, program_id: int, *, ns: str) -> None:
    if not program or int(program_id or 0) <= 0:
        st.info(t("no_program_selected"))
        return

    warning_key = f"{ns}_warning"
    pending_unit_key = f"{ns}_pending_unit"
    original_program = dict(program or {})
    program = normalize_learning_program_output(program)

    pending_unit = st.session_state.get(pending_unit_key)
    if pending_unit:
        pending_unit_data = next(
            (unit for unit in (program.get("units") or []) if int(unit.get("unit_number") or 0) == int(pending_unit)),
            {},
        )
        _render_learning_program_loading_shell(
            t("building_learning_program_unit", unit=pending_unit),
            t(
                "learning_program_loading_unit_detail",
                unit=pending_unit,
                title=_clean_display_text(pending_unit_data.get("title")) or t("learning_program_singular"),
            ),
        )
        with st.status(t("building_learning_program_unit", unit=pending_unit), expanded=True) as status:
            status.write(t("learning_program_loading_previous_context"))
            status.write(t("learning_program_loading_topic_map"))
            status.write(t("learning_program_loading_teacher_student"))
            updated_program, _unit_mode_used, unit_warning = generate_ai_learning_program_unit(
                subject=original_program.get("subject"),
                learner_stage=original_program.get("learner_stage"),
                level_or_band=original_program.get("level_or_band"),
                program=program,
                unit_number=int(pending_unit),
                custom_subject_name=original_program.get("custom_subject_name") or "",
                previous_program=load_learning_program(int(original_program.get("parent_program_id") or 0)) if int(original_program.get("parent_program_id") or 0) > 0 else None,
                payload=None,
            )
            status.update(label=t("learning_program_loading_ready"), state="complete")
        ok, msg = update_learning_program(
            program_id=int(program_id),
            subject=original_program.get("subject"),
            learner_stage=original_program.get("learner_stage"),
            level_or_band=original_program.get("level_or_band"),
            program=updated_program,
            visibility=original_program.get("visibility") or "private",
            source_type=original_program.get("source_type") or "ai",
            custom_subject_name=original_program.get("custom_subject_name") or "",
            status=original_program.get("status") or "draft",
            generation_mode=original_program.get("generation_mode") or "ai",
            program_language=original_program.get("program_language"),
            student_material_language=original_program.get("student_material_language"),
            builder_config=original_program.get("builder_config") or {},
            parent_program_id=original_program.get("parent_program_id"),
            sequence_group_id=original_program.get("sequence_group_id") or "",
            sequence_order=original_program.get("sequence_order"),
            prerequisite_summary=original_program.get("prerequisite_summary") or "",
        )
        st.session_state.pop(pending_unit_key, None)
        if ok:
            st.session_state[warning_key] = unit_warning
        else:
            st.session_state[warning_key] = t("learning_program_update_failed", error=msg)
        st.rerun()

    warning = st.session_state.get(warning_key)
    if warning:
        st.warning(warning)

    ready_units = _count_ready_program_units(program)
    total_units = len(program.get("units") or [])
    if not _program_is_complete(program):
        st.info(t("learning_program_continue_building_note", ready_units=ready_units, total_units=total_units))
    else:
        st.success(t("learning_program_ready_to_publish"))

    render_learning_program_builder_preview(
        program,
        ns,
        saved_program_id=int(program_id),
        edit_meta=original_program,
    )


def load_enriched_program_assignments_for_current_student() -> list[dict]:
    student_id = _clean_text(get_current_user_id())
    if not student_id:
        return []

    assignments_df = load_program_assignments_for_student(student_user_id=student_id)
    if assignments_df is None or assignments_df.empty:
        return []

    enriched: list[dict] = []
    for _, row in assignments_df.iterrows():
        row_dict = row.to_dict()
        program_id = int(row_dict.get("program_id") or 0)
        assignment_id = int(row_dict.get("id") or 0)
        if program_id <= 0 or assignment_id <= 0:
            continue
        program = load_learning_program(program_id)
        if not program:
            continue
        teacher_profile = load_profile_row(_clean_text(row_dict.get("teacher_id")))
        progress_map = load_assignment_progress_map(assignment_id)
        total_topics = _count_program_topics(program)
        done_topics = len([1 for item in progress_map.values() if item.get("is_done")])
        enriched.append(
            {
                **row_dict,
                "program": program,
                "progress_map": progress_map,
                "teacher_name": _clean_display_text(
                    teacher_profile.get("display_name") or teacher_profile.get("username") or teacher_profile.get("email") or t("teacher_label")
                ),
                "subject_display": program.get("subject_display") or _subject_display(program.get("subject"), program.get("custom_subject_name")),
                "total_topics": total_topics,
                "completed_topics": done_topics,
                "progress_pct": int(round((done_topics / total_topics) * 100)) if total_topics else 0,
            }
        )
    return enriched


def render_quick_learning_program_builder_expander() -> None:
    ns = "quick_learning_program"

    with st.expander(f"📚 {t('quick_learning_program_maker')}", expanded=False):
        st.caption(t("quick_learning_program_maker_caption"))

        usage = get_ai_learning_program_usage_status()
        if AI_PROGRAM_LIMITS_ENABLED:
            st.caption(
                t(
                    "ai_plans_left_today",
                    remaining=usage["remaining_today"],
                    limit=AI_PROGRAM_DAILY_LIMIT,
                )
            )
        else:
            st.caption(t("learning_program_testing_mode"))

        subject = st.selectbox(
            t("subject_label"),
            _lp().QUICK_SUBJECTS,
            format_func=_lp().subject_label,
            key=f"{ns}_subject",
        )

        custom_subject_name = ""
        if subject == "other":
            custom_subject_name = st.text_input(t("other_subject_label"), key=f"{ns}_other_subject").strip()

        learner_stage = st.selectbox(
            t("learner_stage"),
            _lp().LEARNER_STAGES,
            format_func=_lp()._stage_label,
            key=f"{ns}_stage",
        )

        generation_path = st.radio(
            t("learning_program_flow_label"),
            options=["standalone", "next_level"],
            horizontal=True,
            format_func=lambda x: t("learning_program_flow_standalone") if x == "standalone" else t("learning_program_flow_next_level"),
            key=f"{ns}_generation_path",
        )

        default_level = _lp().recommend_default_level(subject, learner_stage)
        level_options = _lp().get_level_options(subject)
        previous_program = None
        parent_program_id = None
        sequence_group_id = ""
        sequence_order = None
        prerequisite_summary = ""

        progression_candidates = load_progression_candidates(subject, learner_stage, custom_subject_name) if generation_path == "next_level" else pd.DataFrame()
        if generation_path == "next_level" and progression_candidates.empty:
            st.info(t("learning_program_no_previous"))
            generation_path = "standalone"

        if generation_path == "next_level" and not progression_candidates.empty:
            candidate_options = progression_candidates["id"].astype(int).tolist()
            default_candidate = candidate_options[0]
            selected_previous_id = st.selectbox(
                t("learning_program_previous_program"),
                candidate_options,
                format_func=lambda x: (
                    f"{_clean_display_text(progression_candidates.loc[progression_candidates['id'] == x, 'title'].iloc[0])} · "
                    f"{_clean_text(progression_candidates.loc[progression_candidates['id'] == x, 'level_or_band'].iloc[0])}"
                ),
                key=f"{ns}_previous_program_id",
            )
            previous_program = load_learning_program(int(selected_previous_id))
            parent_program_id = int(selected_previous_id)
            sequence_group_id = _clean_text(previous_program.get("sequence_group_id")) or _make_sequence_group_id(subject, learner_stage, custom_subject_name)
            previous_level = _clean_text(previous_program.get("level_or_band"))
            suggested_next_level = _next_recommended_level(subject, learner_stage, previous_level)
            default_level = suggested_next_level if suggested_next_level in level_options else default_level
            sequence_order = int(previous_program.get("sequence_order") or _level_sequence_order(previous_level)) + 1
            prerequisite_summary = (
                previous_program.get("exit_profile")
                or previous_program.get("scope_and_sequence_rationale")
                or t("learning_program_built_on_previous", title=previous_program.get("title") or t("learning_program_previous_program_fallback"))
            )

            st.markdown(
                f"""
                <div class="classio-program-shell" style="padding:1rem 1.05rem;">
                    <div class="classio-program-kicker">{t("learning_program_progression_foundation")}</div>
                    <div class="classio-program-title" style="font-size:1.05rem;">{previous_program.get('title') or t("learning_program_previous_program_fallback")}</div>
                    <div class="classio-program-tagline">{t("learning_program_progression_levels", current=previous_level, suggested=default_level)}</div>
                    <div class="classio-program-summary">{prerequisite_summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.session_state.get(f"{ns}_level") not in level_options:
            st.session_state[f"{ns}_level"] = default_level

        level_or_band = st.selectbox(
            t("level_or_band"),
            level_options,
            format_func=_lp()._level_label,
            key=f"{ns}_level",
        )

        structure = recommend_program_structure(subject, learner_stage)
        c1, c2 = st.columns(2)
        with c1:
            requested_units = st.slider(
                t("learning_program_number_of_units"),
                min_value=structure["units_min"],
                max_value=structure["units_max"],
                value=structure["units_default"],
                key=f"{ns}_units",
            )
        with c2:
            requested_lessons = st.slider(
                t("learning_program_lessons_per_unit"),
                min_value=structure["lessons_per_unit_min"],
                max_value=structure["lessons_per_unit_max"],
                value=structure["lessons_per_unit_default"],
                key=f"{ns}_lessons_per_unit",
            )

        visibility = st.radio(
            t("learning_program_save_as"),
            options=["private", "public"],
            horizontal=True,
            format_func=lambda x: t("my_learning_programs") if x == "private" else t("community_learning_programs"),
            key=f"{ns}_visibility",
        )
        additional_notes = st.text_area(
            t("learning_program_optional_notes"),
            key=f"{ns}_notes",
            placeholder=t("learning_program_notes_placeholder"),
        ).strip()

        total_topics = requested_units * requested_lessons
        st.caption(
            t(
                "learning_program_recommended_structure",
                units=requested_units,
                lessons=requested_lessons,
                total_topics=total_topics,
            )
        )

        skeleton_request_key = f"{ns}_generate_requested"
        unit_request_key = f"{ns}_pending_unit"

        if st.button(t("generate_learning_program"), key=f"{ns}_generate", use_container_width=True):
            if subject == "other" and not custom_subject_name:
                st.error(t("enter_subject_name"))
            else:
                st.session_state[skeleton_request_key] = {
                    "subject": subject,
                    "learner_stage": learner_stage,
                    "level_or_band": level_or_band,
                    "requested_units": requested_units,
                    "requested_lessons_per_unit": requested_lessons,
                    "custom_subject_name": custom_subject_name,
                    "additional_notes": additional_notes,
                    "visibility": visibility,
                    "generation_path": generation_path,
                    "parent_program_id": parent_program_id,
                    "sequence_group_id": sequence_group_id,
                    "sequence_order": sequence_order or _level_sequence_order(level_or_band),
                    "prerequisite_summary": prerequisite_summary,
                    "previous_program": previous_program,
                }
                st.rerun()

        skeleton_request = st.session_state.get(skeleton_request_key)
        if skeleton_request:
            _render_learning_program_loading_shell(
                t("building_learning_program_skeleton"),
                t(
                    "learning_program_loading_skeleton_detail",
                    units=skeleton_request.get("requested_units"),
                    lessons=skeleton_request.get("requested_lessons_per_unit"),
                ),
            )
            with st.status(t("building_learning_program_skeleton"), expanded=True) as status:
                status.write(t("learning_program_loading_scope"))
                status.write(t("learning_program_loading_sequence"))
                status.write(t("learning_program_loading_teacher_student"))
                program, mode_used, warning, payload = generate_ai_learning_program_skeleton(
                    subject=skeleton_request.get("subject", subject),
                    learner_stage=skeleton_request.get("learner_stage", learner_stage),
                    level_or_band=skeleton_request.get("level_or_band", level_or_band),
                    requested_units=skeleton_request.get("requested_units", requested_units),
                    requested_lessons_per_unit=skeleton_request.get("requested_lessons_per_unit", requested_lessons),
                    custom_subject_name=skeleton_request.get("custom_subject_name", custom_subject_name),
                    additional_notes=skeleton_request.get("additional_notes", additional_notes),
                    previous_program=skeleton_request.get("previous_program"),
                )
                status.update(label=t("learning_program_loading_ready"), state="complete")
            st.session_state[f"{ns}_result"] = program
            st.session_state[f"{ns}_mode_used"] = mode_used
            st.session_state[f"{ns}_warning"] = warning
            st.session_state[f"{ns}_payload"] = payload
            st.session_state[f"{ns}_meta"] = {
                "subject": skeleton_request.get("subject", subject),
                "learner_stage": skeleton_request.get("learner_stage", learner_stage),
                "level_or_band": skeleton_request.get("level_or_band", level_or_band),
                "custom_subject_name": skeleton_request.get("custom_subject_name", custom_subject_name),
                "visibility": skeleton_request.get("visibility", visibility),
                "generation_path": skeleton_request.get("generation_path", generation_path),
                "parent_program_id": skeleton_request.get("parent_program_id"),
                "sequence_group_id": skeleton_request.get("sequence_group_id", ""),
                "sequence_order": skeleton_request.get("sequence_order"),
                "prerequisite_summary": skeleton_request.get("prerequisite_summary", ""),
                "builder_config": {
                    "requested_units": skeleton_request.get("requested_units", requested_units),
                    "requested_lessons_per_unit": skeleton_request.get("requested_lessons_per_unit", requested_lessons),
                    "additional_notes": skeleton_request.get("additional_notes", additional_notes),
                    "generation_path": skeleton_request.get("generation_path", generation_path),
                    "parent_program_id": skeleton_request.get("parent_program_id"),
                },
            }
            st.session_state.pop(skeleton_request_key, None)
            st.rerun()

        result = st.session_state.get(f"{ns}_result")
        if result:
            pending_unit = st.session_state.get(unit_request_key)
            warning = st.session_state.get(f"{ns}_warning")
            mode_used = st.session_state.get(f"{ns}_mode_used", "ai")
            meta = st.session_state.get(f"{ns}_meta", {})
            payload = st.session_state.get(f"{ns}_payload")

            if pending_unit:
                pending_unit_data = None
                for existing_unit in result.get("units") or []:
                    if int(existing_unit.get("unit_number") or 0) == int(pending_unit):
                        pending_unit_data = existing_unit
                        break
                _render_learning_program_loading_shell(
                    t("building_learning_program_unit", unit=pending_unit),
                    t(
                        "learning_program_loading_unit_detail",
                        unit=pending_unit,
                        title=_clean_display_text((pending_unit_data or {}).get("title")) or t("learning_program_singular"),
                    ),
                )
                with st.status(t("building_learning_program_unit", unit=pending_unit), expanded=True) as status:
                    status.write(t("learning_program_loading_previous_context"))
                    status.write(t("learning_program_loading_topic_map"))
                    status.write(t("learning_program_loading_teacher_student"))
                    updated_program, unit_mode_used, unit_warning = generate_ai_learning_program_unit(
                        subject=meta.get("subject", subject),
                        learner_stage=meta.get("learner_stage", learner_stage),
                        level_or_band=meta.get("level_or_band", level_or_band),
                        program=result,
                        unit_number=int(pending_unit),
                        custom_subject_name=meta.get("custom_subject_name", custom_subject_name),
                        additional_notes=meta.get("builder_config", {}).get("additional_notes", additional_notes),
                        previous_program=previous_program,
                        payload=payload,
                    )
                    status.update(label=t("learning_program_loading_ready"), state="complete")
                st.session_state[f"{ns}_result"] = updated_program
                st.session_state[f"{ns}_mode_used"] = "ai" if unit_mode_used != "template" and mode_used == "ai" else mode_used
                st.session_state[f"{ns}_warning"] = unit_warning
                st.session_state.pop(unit_request_key, None)
                result = updated_program
                warning = unit_warning

            generated_units = sum(1 for unit in (result.get("units") or []) if _program_has_generated_unit_details(unit))

            if warning:
                st.warning(warning)
            st.caption(t("learning_program_generation_mode", mode=t("mode_ai") if mode_used == "ai" else t("template_fallback")))
            st.caption(t("learning_program_builder_progress", generated_units=generated_units, total_units=len(result.get("units") or [])))
            render_learning_program_builder_preview(
                result,
                ns,
                edit_meta=meta,
            )

            save_col, clear_col = st.columns(2)
            with save_col:
                if st.button(t("save_learning_program"), key=f"{ns}_save", use_container_width=True):
                    ok, program_id, msg = _save_generated_learning_program_from_builder(
                        result=result,
                        meta=meta,
                        subject=subject,
                        learner_stage=learner_stage,
                        level_or_band=level_or_band,
                        custom_subject_name=custom_subject_name,
                        visibility=visibility,
                        mode_used=mode_used,
                    )
                    if ok:
                        st.session_state[f"{ns}_saved_program_id"] = program_id
                        st.success(t("learning_program_saved_success", program_id=program_id))
                    else:
                        st.error(t("learning_program_save_failed", error=msg))
            with clear_col:
                if st.button(t("clear_builder"), key=f"{ns}_clear", use_container_width=True):
                    for key in [f"{ns}_result", f"{ns}_mode_used", f"{ns}_warning", f"{ns}_meta", f"{ns}_payload", f"{ns}_pending_unit", f"{ns}_saved_program_id"]:
                        st.session_state.pop(key, None)
                    st.rerun()

            st.markdown(f"### {t('assign_to_student')}")
            linked_students = _tsi().load_active_linked_students_for_teacher()
            assignable_students = [row for row in linked_students if _clean_text(row.get("student_name"))]
            if not assignable_students:
                st.info(t("assignment_requires_relationship_message"))
            else:
                student_options = [_clean_text(row.get("student_name")) for row in assignable_students]
                assign_col1, assign_col2 = st.columns([1.4, 1.0])
                with assign_col1:
                    selected_student_name = st.selectbox(
                        t("student_name_label"),
                        student_options,
                        key=f"{ns}_assign_student_name",
                    )
                selected_row = next(
                    (row for row in assignable_students if _clean_text(row.get("student_name")) == selected_student_name),
                    {},
                )
                with assign_col2:
                    assign_note = st.text_input(
                        t("teacher_note"),
                        key=f"{ns}_assign_note",
                        placeholder=t("assignment_teacher_note_placeholder"),
                    ).strip()

                if st.button(t("assign_learning_program_and_save_button"), key=f"{ns}_assign_and_save", use_container_width=True):
                    program_id = st.session_state.get(f"{ns}_saved_program_id")
                    if not program_id:
                        ok, program_id, msg = _save_generated_learning_program_from_builder(
                            result=result,
                            meta=meta,
                            subject=subject,
                            learner_stage=learner_stage,
                            level_or_band=level_or_band,
                            custom_subject_name=custom_subject_name,
                            visibility=visibility,
                            mode_used=mode_used,
                        )
                        if not ok:
                            st.error(t("learning_program_save_failed", error=msg))
                            st.stop()
                        st.session_state[f"{ns}_saved_program_id"] = program_id
                        st.success(t("learning_program_saved_success", program_id=program_id))

                    ok, assignment_id, msg = assign_learning_program(
                        program_id=int(program_id),
                        student_name=selected_student_name,
                        student_user_id=_clean_text(selected_row.get("student_id")),
                        note=assign_note,
                    )
                    if ok:
                        st.success(t("learning_program_assigned_success", student=selected_student_name, assignment_id=assignment_id))
                    else:
                        st.error(t("learning_program_assigned_failed", error=msg))
