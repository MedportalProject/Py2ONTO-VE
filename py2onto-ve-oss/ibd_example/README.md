# Inflammatory Bowel Disease (IBD) Ontology — Biomedical Example

A realistic biomedical domain ontology for Inflammatory Bowel Disease, designed
as a demonstration template for **Py2ONTO Visual Editor**.

## Ontology Scope

This ontology models the domain of Inflammatory Bowel Disease, covering:

- **Disease subtypes** — Crohn's Disease and Ulcerative Colitis
- **Symptoms** — Diarrhea, Stomach Pain, Fatigue, Nausea, Weight Loss
- **Disease Phases** — Remission and Flare-up
- **Complications** — both GI complications (Dehydration, Malabsorption, Increased Cancer Risk) and extraintestinal manifestations (Anemia, Reduced Bone Density, Joint Pain, Skin Changes, Eye Irritation, Delayed Growth)
- **Mental Health** — Depression, Anxiety, Distress, Other Mental Disorders
- **Medications** — Aminosalicylates, Corticosteroids, Immunomodulators, Biologics
- **Treatments** — Surgery

## Class Hierarchy (37 classes)

```
Thing
├── Symptom
│   ├── Diarrhea
│   ├── StomachPain
│   ├── Fatigue
│   ├── Nausea
│   └── WeightLoss
├── DiseasePhase
│   ├── Remission
│   └── FlareUp
├── Complication
│   ├── GastrointestinalComplication
│   │   ├── Dehydration
│   │   ├── Malabsorption
│   │   └── IncreasedCancerRisk
│   └── ExtraintestinalManifestation
│       ├── Anemia
│       ├── ReducedBoneDensity
│       ├── JointPain
│       ├── SkinChanges
│       ├── EyeIrritation
│       └── DelayedGrowth
├── MentalHealthChallenge
│   ├── Depression
│   ├── Anxiety
│   ├── Distress
│   └── OtherMentalDisorder
├── Medication
│   ├── Aminosalicylate
│   ├── Corticosteroid
│   ├── Immunomodulator
│   └── Biologic
├── Treatment
│   └── Surgery
└── disease (MONDO_0000001, external)
    └── InflammatoryBowelDisease
        ├── UlcerativeColitis
        └── CrohnsDisease
```

## Object Properties

| Property           | Domain                    | Range                 | Notes                     |
|--------------------|---------------------------|-----------------------|---------------------------|
| affects            | InflammatoryBowelDisease  | Thing                 | —                         |
| hasSymptom         | InflammatoryBowelDisease  | Symptom               | —                         |
| hasPhase           | InflammatoryBowelDisease  | DiseasePhase          | —                         |
| leadsTo            | InflammatoryBowelDisease  | Complication          | —                         |
| increasesRiskOf    | InflammatoryBowelDisease  | MentalHealthChallenge | —                         |
| treatedBy          | InflammatoryBowelDisease  | Thing                 | —                         |
| isSymptomOf        | (inferred)                | (inferred)            | inverse_of: hasSymptom    |
| isGIComplicationOf | (inferred)                | (inferred)            | —                         |

## How to Use

### Method A: CSV Upload

1. Open the Py2ONTO Visual Editor
2. Set the **IRI** (e.g. `http://bmicc.cn/IBD_py2ontove.owl#`)
3. On each tab, use the **Upload** button to import the corresponding CSV:

   | Tab                   | File                    |
   |-----------------------|-------------------------|
   | Object Properties     | `object_properties.csv` |
   | Classes               | `classes.csv`           |

4. Click **Build** to verify the ontology tree
5. Click **Generate OWL** to save the `.owl` file

### Method B: AI Assist

1. Copy the entire content of [`ai_assist_prompt.txt`](ai_assist_prompt.txt)
2. Open the **AI Assist** tab in the editor
3. Paste the text into the input area
4. Select your LLM provider (DeepSeek recommended)
5. Click **Extract Ontology** — the LLM will auto-populate all tables
6. Review and correct the extracted data, then click **Build**

### Method C: AI Assist with Task Prompt

1. Copy the entire content of [`ai_assist_prompt.txt`](ai_assist_prompt.txt) into the AI input area
2. Click **Task prompt** and paste the content of [`task_prompt.txt`](task_prompt.txt)
3. Select your LLM provider (DeepSeek recommended)
4. Click **Extract Ontology** — the task prompt guides the LLM to follow IBD-specific conventions
5. Review and correct the extracted data, then click **Build**

### Method D: Command Line

```bash
python -c "
from py2onto import Py2ONTO
onto = Py2ONTO('http://bmicc.cn/IBD_py2ontove.owl#')
onto._create_object_property_by_template('ibd_example/object_properties.csv')
onto.init('ibd_example/classes.csv')
onto.save('./ibd_ontology.owl')
"
```

## Pre-built Ontology

The file [`IBD_py2ontove.owl`](IBD_py2ontove.owl) is the generated OWL ontology ready for use in tools like Protégé. The companion [`IBD_py2ontove.txt`](IBD_py2ontove.txt) is the auto-generated metadata report containing statistics, the full class hierarchy as an ASCII tree, property details, and software environment information.

## Design Notes

- `isSymptomOf` is declared as `inverse_of: hasSymptom` — the reasoner infers bidirectional relationships automatically
- Symptom classes use `$isSymptomOf: InflammatoryBowelDisease` to establish explicit instance-level relationships
- GI complications (Dehydration, Malabsorption, IncreasedCancerRisk) use `$isGIComplicationOf: InflammatoryBowelDisease` for direct class-level links
- The ontology models both the disease itself and its broader impact (mental health, quality of life)
