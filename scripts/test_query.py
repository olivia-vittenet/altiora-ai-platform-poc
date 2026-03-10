import json
import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# Fonction utilitaire pour simuler l'ACL check du RAG
def filter_results_by_role(results, user_groups):
    """Filtre les documents FAISS retournés en simulant la vérification Azure AD."""
    authorized_docs = []
    
    for doc in results:
        doc_groups = doc.metadata.get('allowed_groups', [])
        
        # Le User a accès si l'un de ses groupes correspond aux groupes autorisés du Doc
        # Ou si le doc est public pour tous les employés
        if "everybody@altiora.internal" in doc_groups or any(group in doc_groups for group in user_groups):
             authorized_docs.append(doc)
    
    return authorized_docs


def main():
    # 1. Charger les profils utilisateur Mocks
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        users_path = os.path.join(script_dir, "..", "mocks", "users.json")
        with open(users_path, "r", encoding="utf-8") as f:
             users_data = json.load(f)
             dev_profile = users_data["users"][0] # Sophie (Dev)
             hr_profile = users_data["users"][1]  # Marc (HR)
    except Exception as e:
        print(f"Erreur de chargement des profils utilisateurs: {e}")
        return

    # 2. Charger le modèle et l'index
    print("\n[+] Chargement de l'index FAISS local...")
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    vectorstore = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)

    # 3. Requêtes de Test couvrant la Tech et l'Administratif
    queries = [
        "J'ai un problème de rafraîchissement avec le graphique solaire sur iOS, as-tu des pistes ?",
        "Comment fonctionne l'ingestion de données Kafka ?",
        "Je voudrais recruter un développeur Senior en France, quel salaire fixe et prime puis-je lui proposer au maximum ?",
        "Quelle est la politique et l'indemnité pour le télétravail ?"
    ]

    for query in queries:
        print(f"\n=========================================================")
        print(f"QUESTION DU USER: '{query}'")
        print(f"=========================================================")

        # A. Execution de la recherche Sémantique BRUTE (Sans aucune permission de sécurité)
        raw_results = vectorstore.similarity_search(query, k=5) 

        # B. Simulation ChatBot pour la Développeuse (Sophie)
        print(f"\n[DEV] POINT DE VUE DE SOPHIE ( {dev_profile['role']} )")
        print(f"Groupes AD : {dev_profile['aad_groups']}")
        
        dev_allowed_docs = filter_results_by_role(raw_results, dev_profile["aad_groups"])
        if not dev_allowed_docs:
             print("=> [X] L'IA ne trouve aucun document pertinent ou autorisé pour répondre à Sophie.")
        
        for i, doc in enumerate(dev_allowed_docs[:1]): # On n'affiche que le meilleur
            print(f"=> [OK] RESULTAT (Source: {doc.metadata.get('source')} | Secrét: {doc.metadata.get('security_level')})")
            print(f"       Extrait : {doc.page_content[:150]}...")

        # C. Simulation ChatBot pour le RH (Marc)
        print(f"\n[HR] POINT DE VUE DE MARC ( {hr_profile['role']} )")
        print(f"Groupes AD : {hr_profile['aad_groups']}")
        
        hr_allowed_docs = filter_results_by_role(raw_results, hr_profile["aad_groups"])
        if not hr_allowed_docs:
             print("=> ❌ L'IA ne trouve aucun document pertinent ou autorisé pour répondre à Marc.")
             
        for i, doc in enumerate(hr_allowed_docs[:1]):
            print(f"=> [OK] RESULTAT (Source: {doc.metadata.get('source')})")
            print(f"       Extrait : {doc.page_content[:150]}...")


if __name__ == "__main__":
    main()
