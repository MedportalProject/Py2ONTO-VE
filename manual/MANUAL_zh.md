# Py2ONTO Visual Editor — 用户手册

> 基于 Web 的本体（Ontology）编辑器，支持手动填表、CSV 导入导出、OLS 本体术语搜索、AI 自然语言提取，生成标准 OWL 格式文件及配套元数据报告。

---

## 目录

1. [快速开始](#快速开始)
2. [界面概览](#界面概览)
3. [编辑本体](#编辑本体)
   - [Classes（类）](#classes类)
   - [Annotation Properties（注释属性）](#annotation-properties注释属性)
   - [Object Properties（对象属性）](#object-properties对象属性)
   - [Individuals（个体/实例）](#individuals个体实例)
   - [自定义列](#自定义列)
4. [构建与预览](#构建与预览)
5. [生成与下载 OWL 文件](#生成与下载-owl-文件)
6. [CSV 导入导出](#csv-导入导出)
   - [下载 CSV 模板](#下载-csv-模板)
   - [上传 CSV 文件](#上传-csv-文件)
7. [本体术语搜索 (OLS & BioPortal)](#本体术语搜索-ols--bioportal)
8. [AI 辅助提取](#ai-辅助提取)
   - [配置 API Key](#配置-api-key)
   - [使用 AI 提取](#使用-ai-提取)
   - [本体术语映射](#本体术语映射)
   - [自定义 System Prompt](#自定义-system-prompt)
   - [自定义 Task Prompt](#自定义-task-prompt)
   - [支持的 LLM Provider](#支持的-llm-provider)
9. [本体树可视化](#本体树可视化)
10. [配置文件说明](#配置文件说明)
11. [本体文件格式](#本体文件格式)
12. [IBD 示例](#ibd-示例)
13. [Ollama 本地部署](#ollama-本地部署)
14. [常见问题](#常见问题)

---

## 快速开始

> **前提**：Python 3.10 或更高版本。

### 1. 安装依赖

```bash
cd py2onto-oss
pip install -r requirements.txt
```

### 2. 配置 API Key（可选，仅 AI 提取功能需要）

编辑 `config.json`，填入你要使用的 LLM provider 的 API Key。

### 3. 启动服务

```bash
python app.py
```

默认启动在 `http://127.0.0.1:5001`，浏览器打开即可。

---

## 界面概览

界面分为三大区域：

```
┌──────────────────────────────────────────────────────────────────┐
│  工具栏: [IRI 输入]  [Build] [Generate OWL] [Clear]              │
├───────────────────────────┬──────────────────────────────────────┤
│  左面板（6 个 Tab）        │  右面板（本体树可视化）                │
│  ┌──────────────────────┐ │  ┌──────────────────────────────────┐│
│  │ Classes              │ │  │   Thing [root]                   ││
│  │ Annotation Props     │ │  │   ├── Disease                    ││
│  │ Object Props         │ │  │   │   ├── Hypertension           ││
│  │ Individuals          │ │  │   │   └── CAD                    ││
│  │ Ontology Class Search│ │  │   └── Drug                       ││
│  │ AI Assist            │ │  │       ├── Aspirin                ││
│  └──────────────────────┘ │  │       └── ◆ aspirin_01           ││
│                           │  └──────────────────────────────────┘│
└───────────────────────────┴──────────────────────────────────────┘
```

- **工具栏**：设置本体 IRI、构建预览、生成 OWL 文件、清空所有数据
- **左面板**：6 个 Tab，分别编辑 Classes / Annotation Properties / Object Properties / Individuals / 本体术语搜索（OLS 和 BioPortal） / AI 提取（支持 DeepSeek、ChatGLM、Gemini、Ollama）
- **右面板**：本体层级树，点击节点可跳转到对应表格行

---

## 编辑本体

### Classes（类）

类的表格包含以下列：

| 列名 | 说明 | 示例 |
|------|------|------|
| `Parent_Class` | 父类 ID，顶层类填 `Thing` | `Disease` |
| `ID` | 类唯一标识（CamelCase） | `CardiovascularDisease` |
| `label` | 可读标签 | `Cardiovascular Disease` |
| `IRI` | 类的完整 IRI，由「基础 IRI + ID」自动生成，只读不可手动修改。 | `http://example.org/onto.owl#CardiovascularDisease` |
| `comment` | 描述性注释 | `影响心脏或血管的疾病` |
| `definition` | 形式化定义文本 | （可选） |

**IRI 自动生成**：`IRI` 字段为只读，由「\<本体基础 IRI\>\<ID\>」自动生成。当你编辑 `ID` 字段或修改工具栏中的基础 IRI 时，所有本地类的 IRI 会自动同步更新。从 OLS/BioPortal 导入的外部类保留其规范 IRI，不受基础 IRI 变更影响。

**来源标识（Source Badge）**：类可以在标签旁边显示来源标识：
- `local`（默认，不显示标识）—— 本地定义的本体类。
- `OLS`（橙色标识）—— 从 Ontology Lookup Service 导入的类（参见[本体术语搜索](#本体术语搜索-ols--bioportal)）。
- `BioPortal`（绿色标识）—— 从 BioPortal 导入的类。
- 其他来源标识可能出现在外部来源的类中。

**操作**：
- **+ Row**：添加一个空行
- **− Row**：删除选中的行（勾选复选框）
- 直接在单元格中编辑内容

**类名自动补全**：当编辑 `Parent_Class`、`Types`（在 Individuals 中）或属性中的 `domain`/`range` 字段时，会自动弹出已有类 ID 的下拉建议（`Thing` 始终可选）。建议列表会在类添加或删除时自动更新。

### Annotation Properties（注释属性）

用于给本体实体附加描述性元数据，如 `hasDbXref`、`definition`、`hasSynonym` 等。与对象属性不同，注释属性不参与 OWL DL 推理——其 `domain` 和 `range` 仅作文档用途。

| 列名 | 说明 |
|------|------|
| `ID` | 属性标识（lowercase_with_underscores 或 camelCase） |
| `label` | 可读标签 |
| `comment` | 描述 |
| `domain` | 该注释预期适用的类，可用 `&` 串联多个 |
| `range` | 该注释预期的取值类型，可用 `&` 串联多个 |
| `definition` | 形式化定义（可选） |

### Object Properties（对象属性）

用于定义类之间的关系（如 `treats`、`causes`、`hasPart`）。

| 列名 | 说明 |
|------|------|
| `ID` | 属性标识 |
| `label` | 可读标签 |
| `comment` | 描述 |
| `FunctionalProperty` ~ `IrreflexiveProperty` | 属性特性，填 `True` 启用 |
| `equivalent_to` | 等价属性 |
| `subproperty_of` | 父属性 |
| `inverse_of` | 逆属性 |
| `domain` | 定义域（主语类，可用 `&` 串联多个） |
| `range` | 值域（宾语类，可用 `&` 串联多个） |
| `disjoint_with` | 互斥属性 |
| `definition` | 形式化定义（可选） |

**属性特性说明**：

| 特性 | 含义 |
|------|------|
| `FunctionalProperty` | 函数性 |
| `InverseFunctionalProperty` | 逆函数性 |
| `TransitiveProperty` | 传递性 |
| `SymmetricProperty` | 对称性 |
| `AsymmetricProperty` | 非对称性 |
| `ReflexiveProperty` | 自反性 |
| `IrreflexiveProperty` | 非自反性 |

### Individuals（个体/实例）

用于定义类的具体实例。

| 列名 | 说明 |
|------|------|
| `Types` | 所属类的 ID |
| `relation` | 固定为 `has_individual` |
| `ID` | 个体唯一标识 |
| `label` | 可读标签 |
| `comment` | 描述 |
| `definition` | 形式化定义（可选） |

### 自定义列

点击 **+ Col** 可以添加自定义列到任意表格。列名规则：
- 以 `*` 开头：视为注释属性（annotation property），值会作为该属性的取值
- 以 `$` 开头：视为对象属性（object property），格式为 `$属性名.值类名`（如 `$treats.Disease`）

点击 **− Col** 可以删除自定义列，会弹出提示要求输入确切的列名。

---

## 构建与预览

点击工具栏的 **Build** 按钮：
- 后端根据表格数据构建本体
- 右面板展示本体层级树
- 不会保存文件

> **提示**：即使所有表格为空也可以 Build，会生成一个仅含 `Thing` 根节点的空本体树。

---

## 生成与下载 OWL 文件

点击工具栏的 **Generate OWL** 按钮：

1. 弹出对话框询问文件名（默认 `new_onto.owl`）
2. 后端构建本体并保存为 RDF/XML 格式的 `.owl` 文件
3. 同时自动生成一份 `.txt` 元数据报告（与 OWL 文件同名、同目录）
4. 浏览器自动触发下载（OWL 文件 + 元数据报告共两个文件）
5. 按钮和统计栏会显示已用时间计数器（如"Generating… 3.2s"）

**元数据报告包含**：
- 本体 IRI、生成时间、输出文件路径
- 统计信息（类数、个体数、对象属性数、注释属性数）
- ASCII 格式的类层级树
- 每个对象属性的详细信息及其特性
- 每个注释属性的列表
- 软件环境信息（Python 版本、Py2ONTO 版本、owlready2 版本）

---

## CSV 导入导出

### 下载 CSV 模板

每个 Tab 面板都有 **Download** 按钮：
- 点击下载当前表格为 CSV 文件
- 文件命名格式：`<表名>_template.csv`（如 `classes_template.csv`）
- 即使表格为空，也会下载仅含列标题的**空模板**，方便离线填写

### 上传 CSV 文件

每个 Tab 面板都有 **Upload** 按钮：
- 选择对应的 CSV 文件导入
- CSV 的第一行必须是列标题（与下载的模板格式一致）
- 导入的数据会替换当前表格内容
- CSV 中存在但不在内置列中的自定义列会自动添加

**CSV 格式示例**（classes）：

```csv
Parent_Class,ID,label,IRI,comment,definition
Thing,Disease,Disease,http://example.org/onto.owl#Disease,影响生物体正常功能的病理状态,
Disease,Hypertension,Hypertension,http://example.org/onto.owl#Hypertension,血压持续升高,
```

---

## 本体术语搜索 (OLS & BioPortal)

**Ontology Class Search** Tab 提供了内置的 [EBI Ontology Lookup Service (OLS)](https://www.ebi.ac.uk/ols) 和 [BioPortal](https://bioportal.bioontology.org/) 双源搜索接口，方便查找标准本体术语。

### 选择搜索源

在搜索 Tab 顶部，使用单选按钮切换搜索源：

- **OLS (EBI)**（默认）：搜索 EBI Ontology Lookup Service，涵盖 OBO Foundry 系列（>200 个本体），包括 GO、DO、HPO、EFO 等。
- **BioPortal**：搜索 BioPortal 本体仓库（>900 个本体），包括 SNOMED CT、NCIt、MedDRA 等。需要在 `config.json` 中配置 API Key（参见[配置文件说明](#配置文件说明)）。

搜索源切换按钮旁设有**本体过滤器**输入框，可将搜索范围限定到特定本体：
- OLS：输入单个本体前缀（如 `efo`、`go`、`hp`、`doid`）。
- BioPortal：输入一个或多个本体缩写，逗号分隔（如 `SNOMEDCT,NCIT`）。

### 搜索

1. 切换到 **Ontology Class Search** Tab。
2. 输入搜索关键词（如 `lung cancer`、`diabetes`、`hypertension`）—— 至少 2 个字符。
3. 按下 **Enter** 或点击 **Search**。
4. 结果以表格形式展示，包含列：Select、ID、Label、IRI、Ontology（来源本体名称）。

### 插入类

1. 点击单选按钮选中一个结果。
2. 点击 **Insert Selected Class**。
3. 该类被添加到 Classes 表格中：
   - `ID`、`label`、`IRI` 自动填充来自搜索结果。
   - 标签旁显示橙色 `OLS` 或绿色 `BioPortal` 标识，表示来自外部来源。
   - IRI 使用外部本体的规范 IRI（只读，不随基础 IRI 变更而更新）。
4. 重复检查：如果该类的 ID 或 IRI 已存在于表格中，则阻止插入并提示。

### 清空搜索

点击 **Clear** 可重置搜索输入框、结果列表和状态。

---

## AI 辅助提取

在 **AI Assist** Tab 中，可以用自然语言描述领域知识，让 LLM 自动提取本体元素（类、注释属性、对象属性和个体）。

### 配置 API Key

编辑项目根目录下的 `config.json`，在 `llm` 部分填入 API Key：

```json
{
  "llm": {
    "deepseek": {
      "api_key": "sk-your-deepseek-key",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com/v1"
    }
  }
}
```

也可以使用环境变量，无需写入配置文件：

| Provider | 环境变量 |
|----------|----------|
| DeepSeek | `DEEPSEEK_API_KEY` |
| ChatGLM | `CHATGLM_API_KEY` |
| Gemini | `GEMINI_API_KEY` |

### 使用 AI 提取

1. 切换到 **AI Assist** Tab
2. 选择 **Provider**（LLM 提供商）和 **Model**。模型下拉列表会根据所选 Provider 动态更新。
3. 在文本框中用自然语言描述你的领域。文本框内预置了心血管药理学的示例作为占位文本，可直接替换为你自己的描述。也可以点击 **Clear text** 清空输入框。

   > 💡 **提示：** 你可以通过编辑 **System prompt**（提取规则、JSON schema、输出格式）和 **Task prompt**（领域范围、命名规范、每次提取的特定约束）来定制 AI 的提取行为。编辑按钮位于输入框上方。

4. 选择 **Population mode**：
   - **Merge**（默认）：提取结果追加到现有数据。重复的 ID（表格中已存在的）会自动跳过。
   - **Replace**：清空现有数据后填入提取结果。
5. 点击 **Extract Ontology**。
6. 查看提取结果摘要，如有警告会显示在黄色提示框中。
7. 点击 **Populate Tables** 将结果填入表格。视图会自动切换到 Classes Tab。
8. 可选：点击 **Map to Ontology Terms** 将提取的类与 OLS 或 BioPortal 中的标准本体术语对齐（参见[本体术语映射](#本体术语映射)）。

> **提示**：点击 **Clear text** 可以清空输入框。**Dismiss** 按钮隐藏结果面板但不清除提取数据缓存——在下一次提取之前你仍可以点击 Populate Tables。

### 本体术语映射

AI 提取成功后（包含类），会出现 **Map to Ontology Terms** 按钮。该功能可以将提取的类与 OLS (EBI) 和 BioPortal 中的标准本体术语对齐。

1. 点击 **Map to Ontology Terms** 打开本体术语映射弹窗。
2. 在弹窗顶部选择搜索源：**OLS (EBI)**、**BioPortal** 或 **All Sources**。可选择性为各搜索源指定本体过滤器。
3. 点击 **Begin Search**，系统会用每个提取的类标签去搜索选定的知识门户。
4. 弹窗分为两个面板：
   - **左侧面板**：列出所有已提取的类。每个类显示状态标识（`pending` → `local` 或 `OLS` / `BioPortal`）。
   - **右侧面板**：显示选中类的候选术语，包括 **Keep Local** 选项（默认）和搜索结果。
5. 点击左侧的类可查看其候选术语。
6. 为每个类选择：
   - **Keep Local** —— 保留 AI 生成的 ID、label 和 IRI 不变。
   - **候选术语** —— 将类的 ID、label 和 IRI 替换为标准本体术语。该类会获得 `OLS` 或 `BioPortal` 来源标识。
7. 左侧标识会更新以反映你的选择（`local`、`OLS` 或 `BioPortal`）。
8. 审查完所有类后，点击 **Insert Selected Classes**。
9. 类被添加到 Classes 表格。当替换改变了类 ID 时，父子关系会自动重新映射。
10. 表格中已存在的重复类会被跳过并提示。

### 自定义 System Prompt

点击 **✎ Edit Prompt** 打开 Prompt 编辑弹窗：
- 查看和编辑发送给 LLM 的完整 System Prompt。
- **↺ Reset to Default**：恢复为内置默认 Prompt（需确认）。
- **Save & Close**：保存编辑后的 Prompt 到 `config.json`，之后持续生效。
- 弹窗底部会显示 Prompt 当前状态（"Built-in default loaded" 或 "Custom prompt loaded"）。
- 自定义 Prompt 也会随每次提取请求发送（即使未保存到配置文件）。

### 自定义 Task Prompt

点击输入框上方的 **✎ Task prompt**（位于 System prompt 按钮旁边）打开 Task Prompt 编辑弹窗：

- **Task prompt** 是一组附加到 System Prompt 之后的每次提取指令。用于约束特定提取的范围——例如设定顶层类、限制层级深度、或为该次领域描述提供命名规范。
- 编辑弹窗支持查看、编辑、保存和清除 Task prompt。
- **Save & Close**：保存编辑后的 Task prompt 到 `config.json`，之后持续生效。
- **Clear**：清除 Task prompt，下次提取时不附加额外指令。
- 与 System prompt（定义通用的提取规则和 JSON schema）不同，Task prompt 是任务特定的——你可以根据每次建模的领域不同来调整它。

> 💡 **提示：** AI Assist Tab 的输入框下方有一行提醒，其中包含可点击的链接，可快速打开 System prompt 和 Task prompt 编辑器——方便每次提取前调整提取行为。

### 支持的 LLM Provider

| Provider | 可用模型 | API 类型 |
|----------|---------|----------|
| **DeepSeek** | `deepseek-chat` (DeepSeek-V3), `deepseek-reasoner` (DeepSeek-R1) | OpenAI 兼容 |
| **ChatGLM (智谱)** | `glm-4-flash` (快速), `glm-4`, `glm-4-plus` (最强) | OpenAI 兼容 |
| **Gemini (Google)** | `gemini-2.5-flash` (推荐), `gemini-2.5-pro` (复杂本体) | Google Generative AI SDK |
| **Ollama (本地)** | 任意已拉取的本地模型（如 `llama3`、`mistral`、`qwen2.5`）——模型列表从 Ollama 服务自动获取 | OpenAI 兼容 (localhost:11434) |

> **注意**：使用 Ollama 时，请确保 `ollama serve` 已在本地运行——可用模型会自动出现在模型下拉列表中。

---

## 本体树可视化

右面板展示构建后的本体层级结构：

- **类层级**：可展开/折叠的树形结构，根节点为 `Thing`
  - `●` 类节点：可点击跳转到 Classes 表格中对应行
  - `◆` 个体节点：可点击跳转到 Individuals 表格中对应行
  - `[OLS]` 标识：内联显示在从 OLS 或其他外部本体导入的类旁
- **Object Properties**：以 `↦` 标记，显示定义域和值域
- **Annotation Properties**：以 `@` 标记
- 顶部统计栏：类数 · 个体数 · 对象属性数 · 注释属性数

---

## 配置文件说明

`config.json` 结构：

```json
{
  "medportal": {
    "url": "http://medportal.bmicc.cn:8080",
    "api_key": ""
  },
  "bioportal": {
    "url": "http://data.bioontology.org",
    "api_key": ""
  },
  "system_prompt": "",
  "task_prompt": "",
  "llm": {
    "provider": "deepseek",
    "deepseek": { "api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1" },
    "chatglm":  { "api_key": "", "model": "glm-4-flash", "base_url": "https://open.bigmodel.cn/api/paas/v4" },
    "gemini":   { "api_key": "", "model": "gemini-2.5-flash" },
    "ollama":   { "api_key": "", "model": "", "base_url": "http://localhost:11434/v1" }
  }
}
```

- `medportal` / `bioportal`：MedPortal / BioPortal 本体服务配置（用于 py2onto 核心引擎和 Ontology Class Search Tab 的外部术语搜索）
- `system_prompt`：自定义 LLM System Prompt（通过 AI Assist → ✎ System prompt 编辑）
- `task_prompt`：自定义每次提取的 Task 指令（通过 AI Assist → ✎ Task prompt 编辑）
- `llm.provider`：默认 LLM provider 标识
- `llm.<provider>`：各 LLM provider 的 API Key、模型和 Base URL（如适用）配置
- `llm.ollama`：无需真实 API Key，填入任意占位值即可（如 `"ollama"`）。`base_url` 默认为 `http://localhost:11434/v1`。模型下拉列表会自动检测本地可用模型

---

## 本体文件格式

生成的 `.owl` 文件采用 **RDF/XML** 格式，符合 OWL 2 标准，可在以下工具中打开：

- [Protégé](https://protege.stanford.edu/)
- [WebProtégé](https://webprotege.stanford.edu/)
- 任何支持 OWL 的本体编辑器

同时生成的 `.txt` 元数据报告是纯文本格式。

---

## IBD 示例

`ibd_example/` 目录包含一个完整的 **炎症性肠病 (Inflammatory Bowel Disease, IBD) 本体** 工作示例。它建模了 IBD 亚型、症状、疾病阶段、并发症（消化道及肠外表现）、心理健康影响、药物和治疗。你可以用它来快速上手工具，或作为自己本体项目的模板。

### 本体设计

**37 个类**，分为八个顶层分支（含 1 个外部引用类 `disease`/MONDO）：

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
└── disease（外部引用：MONDO）
    └── InflammatoryBowelDisease
        ├── UlcerativeColitis
        └── CrohnsDisease
```

**8 个对象属性**，涵盖疾病-症状、疾病-阶段、疾病-并发症、疾病-治疗等关系：

| 属性 | 定义域 | 值域 | 特性 |
|---|---|---|---|
| `affects` | InflammatoryBowelDisease | Thing | — |
| `hasSymptom` | InflammatoryBowelDisease | Symptom | — |
| `hasPhase` | InflammatoryBowelDisease | DiseasePhase | — |
| `leadsTo` | InflammatoryBowelDisease | Complication | — |
| `increasesRiskOf` | InflammatoryBowelDisease | MentalHealthChallenge | — |
| `treatedBy` | InflammatoryBowelDisease | Thing | — |
| `isSymptomOf` | (推断) | (推断) | `inverse_of: hasSymptom` |
| `isGIComplicationOf` | (推断) | (推断) | — |

### 文件清单

| 文件 | 说明 |
|------|------|
| `ibd_example/README.md` | 示例完整文档 |
| `ibd_example/classes.csv` | 37 个类定义 |
| `ibd_example/object_properties.csv` | 8 个对象属性定义 |
| `ibd_example/ai_assist_prompt.txt` | AI 提取用的自然语言 Prompt |
| `ibd_example/task_prompt.txt` | AI 提取用的任务特定指令 |
| `ibd_example/IBD_py2ontove.owl` | 预构建的 OWL 本体（可直接用 Protégé 打开） |
| `ibd_example/IBD_py2ontove.txt` | 自动生成的元数据报告 |

### 使用方式

**方式一 — CSV 上传**（确定性）：

1. 打开编辑器，设置 IRI 为 `http://bmicc.cn/IBD_py2ontove.owl#`
2. 在每个 Tab 点击 **Upload** 导入对应 CSV —— 建议按 OPs → Classes 顺序
3. 点击 **Build** 查看本体树 → 点击 **Generate OWL** 导出

**方式二 — AI 辅助提取**（自然语言，演示 LLM 提取能力）：

1. 切换到 **AI Assist** Tab，选择 LLM Provider
2. 将 `ibd_example/ai_assist_prompt.txt` 全文粘贴到输入框
3. 点击 **Extract Ontology** → 查看警告 → 点击 **Populate Tables**
4. 点击 **Build**，验证层级结构与 CSV 导入版本一致

**方式三 — AI 辅助提取 + Task Prompt**（引导式提取）：

1. 将 `ibd_example/ai_assist_prompt.txt` 粘贴到 AI 输入框
2. 点击 **Task prompt**，粘贴 `ibd_example/task_prompt.txt` 的内容
3. 选择 LLM Provider，点击 **Extract Ontology** —— Task prompt 会引导 LLM 遵循 IBD 特定的约定

**方式四 — 命令行**（编程方式使用）：

```bash
python -c "
from py2onto import Py2ONTO
onto = Py2ONTO('http://bmicc.cn/IBD_py2ontove.owl#')
onto._create_object_property_by_template('ibd_example/object_properties.csv')
onto.init('ibd_example/classes.csv')
onto.save('./ibd_ontology.owl')
"
```

以上方式生成的本体完全相同。

---

## Ollama 本地部署

[Ollama](https://ollama.com) 让你可以在本地机器上运行 LLM——无需云端 API Key，也无需互联网连接。Py2ONTO 将 Ollama 作为一等公民的 AI 提取 Provider 来支持。

### 1. 安装 Ollama

**Linux / WSL：**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**macOS：** 从 [ollama.com](https://ollama.com) 下载，或使用 `brew install ollama`。

**Windows：** 从 [ollama.com](https://ollama.com) 下载安装包。

### 2. 启动 Ollama 服务

```bash
ollama serve
```

服务默认监听 `http://localhost:11434`。保持该终端运行。

### 3. 拉取模型

选择适合结构化 JSON 提取的模型。推荐：

```bash
# 通用模型（速度与质量兼顾）
ollama pull llama3.1:8b          # ~4.7 GB
ollama pull qwen2.5:14b          # ~8.5 GB

# 更大模型（质量更好，需要更多内存）
ollama pull qwen2.5:32b          # ~19 GB
ollama pull llama3.1:70b         # ~40 GB

# 较小模型（速度更快，质量稍低）
ollama pull qwen2.5:7b           # ~4.4 GB
ollama pull mistral:7b           # ~4.1 GB
```

验证已安装的模型：

```bash
ollama list
```

### 4. 配置 Py2ONTO 使用 Ollama

编辑 `config.json`：

```json
{
  "llm": {
    "provider": "ollama",
    "ollama": {
      "api_key": "",
      "model": "qwen2.5:14b",
      "base_url": "http://localhost:11434/v1"
    }
  }
}
```

- `api_key`：本地 Ollama 不需要 —— 程序会自动使用占位值。留空即可。
- `model`：任意已拉取的模型名称（如 `llama3.1:8b`、`qwen2.5:14b`、`mistral:7b`）。
- `base_url`：默认为 `http://localhost:11434/v1`。仅当 Ollama 运行在其他主机或端口时才需修改。

> **提示**：也可以通过环境变量 `OLLAMA_API_KEY` 设置（可选 —— 本地 Ollama 不需要）。

### 5. 在编辑器中使用 Ollama

1. 启动编辑器：`python app.py`
2. 切换到 **AI Assist** Tab
3. 从 Provider 下拉列表中选择 **Ollama (Local)**
4. Model 下拉列表会自动检测 Ollama 服务器上可用的模型（需要 `ollama serve` 处于运行状态）
5. 如果下拉列表为空或显示错误，请检查：
   - `ollama serve` 是否在运行（`curl http://localhost:11434/api/tags` 应返回 JSON）
   - 模型是否已拉取（`ollama list`）

### 6. 硬件要求

| 模型大小 | 最低内存 | 推荐内存 |
|----------|----------|----------|
| 7B–8B | 8 GB | 16 GB |
| 14B | 16 GB | 32 GB |
| 32B–70B | 32 GB | 64 GB+ |

- GPU **不是必须的**，但可以显著提升速度。Ollama 会自动使用 NVIDIA/CUDA、AMD/ROCm 或 Apple Metal（如有）。
- CPU 推理对 7B–14B 模型可用，但提取任务会比较慢（预计每次提取 30–120 秒）。

### 7. 常见故障排除

| 问题 | 解决方案 |
|------|----------|
| "Cannot connect to Ollama" | 在另一个终端运行 `ollama serve` |
| 模型未出现在下拉列表中 | 运行 `ollama pull <模型名>` 后刷新 |
| 提取结果 JSON 格式错误 | 尝试更大的/质量更高的模型（如用 `qwen2.5:14b` 替代 `qwen2.5:7b`） |
| 内存不足 | 使用更小的模型或增加 RAM/swap 空间 |
| CPU 模式下 Ollama 速度慢 | 减小模型规模；7B–8B 模型在 CPU 上可用 |

---

## 常见问题

### Q: 没有填任何数据，可以生成 OWL 文件吗？

可以。点击 **Generate OWL** 会生成一个仅包含 IRI 的基础（空）本体文件。

### Q: 如何离线编辑数据？

点击每个 Tab 的 **Download** 按钮下载 CSV 模板，在 Excel 或其他表格工具中编辑后，用 **Upload** 按钮导入。

### Q: AI 提取失败怎么办？

1. 检查 `config.json` 中的 API Key 是否正确
2. 确认网络能访问对应 LLM provider 的 API
3. 尝试用更详细的自然语言描述
4. 查看黄色警告框中的提示（可能 JSON 解析失败）
5. 更换其他 LLM provider 尝试

### Q: 如何添加多个定义域/值域？

在 `domain` 或 `range` 字段中使用 `&` 分隔多个类，例如 `Drug&Device`。

### Q: 生成的文件存在哪里？

文件保存在项目根目录下（`save_path` 参数），浏览器也会自动触发下载 `.owl` 和 `.txt` 两个文件。

### Q: 支持哪些 Python 版本？

Python 3.10+。

### Q: 如何使用外部标准本体术语？

使用 **Ontology Class Search** Tab 搜索 EBI Ontology Lookup Service (OLS) 或 BioPortal，选中匹配的术语后点击 **Insert Selected Class** 即可添加到 Classes 表格，该类会带有 `OLS` 或 `BioPortal` 标识。此外，在 AI 提取后可使用 **Map to Ontology Terms** 功能将提取的类与 OLS 和 BioPortal 标准术语对齐。

### Q: IRI 自动生成是如何工作的？

`IRI` 字段为只读，由「\<本体基础 IRI\>\<ID\>」自动生成。当你修改 `ID` 或工具栏中的基础 IRI 时，所有本地类的 IRI 会自动同步更新。从 OLS/BioPortal 导入的外部类保留其规范 IRI，不受基础 IRI 变更影响。

### Q: AI 提取 Merge 模式下重复的 ID 会怎么处理？

在 **Merge** 模式下，`Populate Tables` 功能会自动跳过目标表格中已存在的 ID。页面会弹出通知显示跳过了多少个重复项。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Flask |
| 本体引擎 | Py2ONTO, owlready2 |
| 数据处理 | pandas |
| 前端 | 原生 HTML / CSS / JavaScript |
| LLM 集成 | OpenAI SDK / Google Generative AI SDK |
| 外部术语服务 | EBI Ontology Lookup Service (OLS), BioPortal |

---

## 项目结构

```
py2onto-oss/
├── app.py                # Flask 主应用（路由、树构建、报告生成）
├── onto_extractor.py     # LLM 本体提取模块
├── config.py             # 配置加载模块
├── config.json           # 用户配置文件（API Key 等）
├── config.example.json   # 配置文件模板
├── py2onto.py            # 核心本体构建引擎
├── requirements.txt      # Python 依赖列表
├── templates/
│   └── index.html        # 前端单页
├── static/
│   ├── css/style.css     # 样式
│   └── js/app.js         # 前端逻辑
├── ibd_example/          # IBD 本体示例（CSV 模板 + AI Prompt）
│   ├── README.md
│   ├── classes.csv
│   ├── object_properties.csv
│   ├── ai_assist_prompt.txt
│   ├── task_prompt.txt
│   ├── IBD_py2ontove.owl
│   └── IBD_py2ontove.txt
├── MANUAL_zh.md          # 中文用户手册（本文件）
└── MANUAL_en.md          # 英文用户手册
```
