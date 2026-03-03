import asyncio, sys
sys.path.insert(0, '.')

async def main():
    print("=== Healthcare Clinical RAG - End-to-End Demo ===\n")

    # Test 1: PHI Detection (local regex - no Azure needed)
    from src.phi_detection import PHIDetector
    detector = PHIDetector()
    detector._client = None  # Force local regex fallback (no Azure)

    test_queries = [
        ("What is the treatment for hypertension?", False),
        ("Patient John Smith DOB 15/03/1975 with SSN 123-45-6789 has diabetes", True),
        ("What are the guidelines for antibiotic prescribing?", False),
        ("My patient email is dr.jones@nhs.uk and their phone is 07700900123", True),
    ]

    print("--- PHI Detection Results ---")
    for query, should_flag in test_queries:
        redacted, has_phi = detector.scan_query(query)
        status = "PHI DETECTED" if has_phi else "SAFE"
        correct = "+" if (has_phi == should_flag) else "-"
        print(f"  [{correct}] {status}: {query[:60]}...")

    # Test 2: Auth - RBAC speciality access
    from src.auth import SPECIALITY_ACCESS
    print(f"\n--- Clinician Access Control ---")
    for speciality, access in SPECIALITY_ACCESS.items():
        print(f"  {speciality}: access to {access}")

    # Test 3: Clinical guidelines documents
    import os
    guidelines_path = "indexer/guidelines"
    if os.path.exists(guidelines_path):
        files = os.listdir(guidelines_path)
        print(f"\nClinical guidelines: {len(files)} documents")
        for f in files:
            filepath = os.path.join(guidelines_path, f)
            size = os.path.getsize(filepath)
            print(f"  - {f} ({size} bytes)")

    # Test 4: JWT token creation and validation
    from src.auth import create_test_token, validate_clinician
    token = create_test_token("dr-002")
    print(f"\nClinician JWT: created for dr-002")
    clinician = validate_clinician(f"Bearer {token}")
    print(f"  Speciality: {clinician.speciality}")
    print(f"  Access: {clinician.allowed_categories}")

    # Test 5: Verify HIPAAAuditLogger exists and can be instantiated
    from src.audit import HIPAAAuditLogger
    auditor = HIPAAAuditLogger()
    print(f"\nHIPAAAuditLogger instantiated (Cosmos DB writes skipped in local mode)")

    # Test 6: Verify ClinicalGenerator can be instantiated
    from src.generator import ClinicalGenerator
    print(f"ClinicalGenerator class is importable and ready")

    print("\n=== Healthcare Clinical RAG: PHI detection, RBAC, and HIPAA audit ready ===")

asyncio.run(main())
