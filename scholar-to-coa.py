# inspired by https://andrew-s-rosen.github.io/coapy/reference/coapy/scholar.html
# modified to find and output affiliations
# for pubmed only, you may want to try: https://bit.ly/NSF_COA
import csv
import time
import argparse
import datetime
from scholarly import scholarly
from tqdm import tqdm

def get_scholar_profile(scholar_id):
    """Retrieve Google Scholar profile by Scholar ID."""
    author = scholarly.search_author_id(scholar_id)
    return scholarly.fill(author) if author else None

def _nsf_name_cleanup(coauthors: list[str]) -> list[str]:
    """Clean up names to be in the NSF format of 'Lastname, Firstname Middle'."""
    cleaned_coauthors = []
    for coauthor in coauthors:
        name_parts = coauthor.split(" ")
        if len(name_parts) > 1:
            reordered_name = f"{name_parts[-1]}, {' '.join(name_parts[:-1])}"
        else:
            reordered_name = coauthor  # Handle single-word names
        cleaned_coauthors.append(reordered_name)
    return cleaned_coauthors

def _get_unique_coauthors(papers, year_cutoff, my_name):
    """
    Extract unique co-authors from recent publications (filtered by year).
    """
    unique_coauthors = {}
    current_year = datetime.datetime.now().year
    filtered_papers = [
        p for p in papers if int(p.get("bib", {}).get("pub_year", current_year)) >= year_cutoff
    ]

    print(f"Processing {len(filtered_papers)} recent publications from {year_cutoff} onward...")
    for paper in tqdm(filtered_papers, desc="Extracting unique co-authors", unit="paper"):
        paper_full = scholarly.fill(paper, sections=["bib"])
        if "author" in paper_full["bib"]:
            coauthors = paper_full["bib"]["author"].split(" and ")
            paper_year = paper_full["bib"].get("pub_year", "Unknown")

            for coauthor in coauthors:
                if coauthor == my_name:
                    continue  # Skip self

                # Store the most recent publication year for each co-author
                if coauthor in unique_coauthors:
                    unique_coauthors[coauthor].add(paper_year)
                else:
                    unique_coauthors[coauthor] = {paper_year}

    return { _nsf_name_cleanup([name])[0]: titles for name, titles in unique_coauthors.items() }

def _get_validated_affiliations(coauthors_with_years):
    """
    Search Google Scholar for each co-author, validate them based on shared publications,
    and find their most recent publication year.
    """
    coauthors_with_affiliations = {}

    print(f"Validating and fetching affiliations for {len(coauthors_with_years)} co-authors...")
    for coauthor, pub_years in tqdm(coauthors_with_years.items(), desc="Validating co-authors", unit="author"):
        try:
            search_results = scholarly.search_author(coauthor)
            validated_affiliation = "Unknown Institution"
            latest_pub_year = max(pub_years) if pub_years else "Unknown"

            for result in search_results:
                author_filled = scholarly.fill(result)
                affiliation = author_filled.get("affiliation", "Unknown Institution")

                # Validate the author by checking for at least one matching publication
                for pub in author_filled.get("publications", []):
                    pub_year = pub.get("bib", {}).get("pub_year", "Unknown")
                    if pub_year in pub_years:
                        validated_affiliation = affiliation
                        break  # Stop searching after first validated match

                if validated_affiliation != "Unknown Institution":
                    break  # Stop searching authors after first validated match

            coauthors_with_affiliations[coauthor] = (validated_affiliation, latest_pub_year)

            # Avoid hitting API rate limits
            time.sleep(1)

        except Exception as e:
            print(f"Error retrieving {coauthor}: {e}")
            coauthors_with_affiliations[coauthor] = ("Unknown Institution", "Unknown")

    return coauthors_with_affiliations

def save_coa_tsv(coauthors_with_affiliations, filename="NSF_COA.tsv"):
    """Save the COA list to a TSV file with the correct format."""
    with open(filename, "w", newline="") as tsvfile:
        writer = csv.writer(tsvfile, delimiter="\t")  # Use tab delimiter for TSV
        for name, (affiliation, pub_date) in coauthors_with_affiliations.items():
            writer.writerow(["A:", name, affiliation, "", pub_date])

    print(f"COA file saved as {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a COA (Collaborators and Other Affiliations) list for NSF from Google Scholar data.")
    parser.add_argument("--scholar-id", type=str, help="Google Scholar ID", default="3HU8c9EAAAAJ")
    parser.add_argument("--years-back", type=int, default=4, help="Number of years to look back for publications (default: 4)")
    parser.add_argument("--output", type=str, default="NSF_COA.tsv", help="Output TSV filename (default: NSF_COA.tsv)")

    args = parser.parse_args()

    print(f"Retrieving Google Scholar profile for ID: {args.scholar_id}...")
    profile = get_scholar_profile(args.scholar_id)

    if profile:
        my_name = profile.get("name", None)
        print(f"Profile found! Automatically removing your name: {my_name}")

        year_cutoff = datetime.datetime.now().year - args.years_back
        print(f"Extracting unique co-authors from {year_cutoff} onward...")
        unique_coauthors_with_years = _get_unique_coauthors(profile["publications"], year_cutoff, my_name)

        print("Validating affiliations for co-authors...")
        coauthors_with_affiliations = _get_validated_affiliations(unique_coauthors_with_years)

        save_coa_tsv(coauthors_with_affiliations, filename=args.output)
    else:
        print("No profile found. Check the Scholar ID.")
