import json
import os
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import boto3

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
MOCKS_DIR = SCRIPT_DIR.parent / "mocks"
FAISS_INDEX_PATH = "faiss_index"
S3_BUCKET = "altiora-storage-2026" 

def load_json(filepath: Path) -> Dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def is_eligible_for_ingestion(acl_metadata: Dict) -> bool:
    """Check if the document is eligible for AI ingestion based on mock metadata."""
    if not acl_metadata or "ai_ingestion" not in acl_metadata:
        return True # Default to eligible if no explicit restriction
    
    return acl_metadata["ai_ingestion"].get("is_eligible", False)

def process_jira_issues() -> List[Document]:
    """Charge jira_full_export.json et extrait la description et métadonnées."""
    print("Traitement de jira_full_export.json ...")
    docs = []
    filepath = MOCKS_DIR / "jira_full_export.json"
    if not filepath.exists():
        print(f"Fichier introuvable: {filepath}")
        return docs
        
    data = load_json(filepath)
    for issue in data.get("issues", []):
        acl = issue.get("__mock_acl", {})
        if not is_eligible_for_ingestion(acl):
            print(f"  [IGNORE] Jira {issue.get('key')}: Non éligible ({acl.get('ai_ingestion', {}).get('reason')})")
            continue
            
        fields = issue.get("fields", {})
        
        # Extraction du texte utile (description)
        description = fields.get("description", "")
        if isinstance(description, dict): 
            description = json.dumps(description)
            
        content = f"Titre: {fields.get('summary', '')}\nDescription: {description}"
        
        # Mapping des métadonnées (security_level, project, department)
        security_level = acl.get("classification", "Public")
        project = fields.get("project", {}).get("key", "UNKNOWN")
        department = "Engineering" if "HR" not in project else "HR"
        
        metadata = {
            "source": f"jira:{issue.get('key')}",
            "type": "issue",
            "security_level": security_level,
            "project": project,
            "department": department,
            "allowed_groups": acl.get("allowed_aad_groups", [])
        }
        
        docs.append(Document(page_content=content, metadata=metadata))
        
    return docs

def process_confluence_pages() -> List[Document]:
    """Charge confluence_full_export.json et extrait la valeur brute (value) et métadonnées."""
    print("Traitement de confluence_full_export.json ...")
    docs = []
    filepath = MOCKS_DIR / "confluence_full_export.json"
    if not filepath.exists():
        print(f"Fichier introuvable: {filepath}")
        return docs
        
    data = load_json(filepath)
    for page in data.get("results", []):
        acl = page.get("__mock_acl", {})
        if not is_eligible_for_ingestion(acl):
            print(f"  [IGNORE] Confluence {page.get('title')}: Non éligible ({acl.get('ai_ingestion', {}).get('reason')})")
            continue
            
        # Extraction de la value (HTML/Texte brut)
        content = page.get("body", {}).get("storage", {}).get("value", "")
        
        # Mapping des métadonnées
        security_level = acl.get("classification", "Public")
        project = page.get("space", {}).get("key", "UNKNOWN")
        department = "HR" if project == "HR" else "Engineering/Product"
        
        metadata = {
            "source": f"confluence:{page.get('id')}",
            "type": "page",
            "title": page.get("title"),
            "security_level": security_level,
            "project": project,
            "department": department,
            "allowed_groups": acl.get("allowed_aad_groups", [])
        }
        
        docs.append(Document(page_content=content, metadata=metadata))
        
    return docs

def process_gitlab_files() -> List[Document]:
    """Charge gitlab.json en simulant un retour d'API (fichiers repository_files)."""
    print("Traitement de gitlab.json (Simulation API GitLab) ...")
    docs = []
    filepath = MOCKS_DIR / "gitlab.json"
    if not filepath.exists():
        print(f"Fichier introuvable: {filepath}")
        return docs

    data = load_json(filepath)
    
    # Process raw repository files from JSON (simulating GET /projects/:id/repository/files API)
    for file in data.get("repository_files", []):
        acl = file.get("__mock_acl", {})
        if not is_eligible_for_ingestion(acl):
            print(f"  [IGNORE] GitLab {file.get('file_path')}: Non éligible ({acl.get('ai_ingestion', {}).get('reason')})")
            continue
            
        # Mapping des métadonnées
        security_level = acl.get("classification", "Public")
        project_id = str(file.get("project_id", "UNKNOWN"))
        # Simuler le département (56 était notre repo RH)
        department = "HR" if project_id == "56" else "Engineering"
            
        metadata = {
            "source": f"gitlab:project_{project_id}:{file.get('file_path')}",
            "type": "code",
            "security_level": security_level,
            "project": f"Project_{project_id}",
            "department": department,
            "filename": file.get("file_name"),
            "allowed_groups": acl.get("allowed_aad_groups", [])
        }
        
        content = file.get("content", "")
        docs.append(Document(page_content=content, metadata=metadata))
                
    return docs

def chunk_documents(docs: List[Document]) -> List[Document]:
    """Découpe les textes en blocs de 800 caractères avec un chevauchement de 100."""
    print(f"Découpage stratégique (Chunking) de {len(docs)} documents (800/100) ...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
    )
    chunks = text_splitter.split_documents(docs)
    print(f"Création de {len(chunks)} blocs isolés terminisée.")
    return chunks

def extract_and_index():
    # 1. Traitement des sources (Extraction & Filtrage)
    docs = []
    docs.extend(process_jira_issues())
    docs.extend(process_confluence_pages())
    docs.extend(process_gitlab_files())
    
    if not docs:
        print("Aucun document trouvé. Vérifiez les chemins des fichiers.")
        return
        
    print(f"\n=> {len(docs)} documents originaux éligibles chargés.")
    
    # 2. Chunking Stratégique (800 / 100)
    chunks = chunk_documents(docs)
    
    # Aperçu du 1er chunk pour vérification
    print("\n--- TEST: APERÇU DU PREMIER BLOC (CHUNK) ---")
    print(f"Contenu : {chunks[0].page_content[:150]}...")
    print(f"Métadonnées (Access Control): {chunks[0].metadata}")
    print("------------------------------------------\n")

    # 3. Embedding Vectoriel (sentence-transformers)
    print("Initialisation du modèle d'Embeddings (HuggingFace)...")
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    
    # 4. Base de Données Vectorielle (FAISS)
    print("Création de l'index FAISS en cours...")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    
    print(f"Sauvegarde locale de l'index dans le dossier '{FAISS_INDEX_PATH}'...")
    vectorstore.save_local(FAISS_INDEX_PATH)
    
    upload_to_s3()
    
def upload_to_s3():
    """Uploade l'index FAISS vers un bucket AWS S3 via boto3."""
    print(f"\n=> Etape 3: Stockage Vectoriel AWS S3")
    print(f"Préparation de l'upload vers le bucket: {S3_BUCKET}...")
    
    # L'index FAISS génère toujours deux fichiers : index.faiss et index.pkl
    files_to_upload = [
        f"{FAISS_INDEX_PATH}/index.faiss",
        f"{FAISS_INDEX_PATH}/index.pkl"
    ]
    
    try:
        # Initialisation du client Boto3 (Nécessite aws configure sur votre terminal)
        s3_client = boto3.client('s3')
        
        for file in files_to_upload:
            if os.path.exists(file):
                filename = os.path.basename(file)
                print(f"  - Upload de {filename} en cours...")
                # Format: upload_file(Fichier_Local, Nom_Bucket, Chemin_Sur_S3)
                s3_client.upload_file(file, S3_BUCKET, filename)
                print(f"    ✔ {filename} uploadé avec succès.")
            else:
                print(f"  [ERREUR] Impossible de trouver le fichier {file}.")
                
        print("\n=> Stockage Vectoriel distant terminé !")
        
    except Exception as e:
        print(f"\n[Avertissement AWS] L'upload S3 a échoué. "
              f"Cela est normal si vous n'avez pas encore configuré vos identifiants AWS Free Tier (aws configure).\n"
              f"Erreur technique: {e}")

if __name__ == "__main__":
    extract_and_index()
    print("\n--- Pipeline d'ingestion terminé avec succès ! ---")
