from input_validator import InputValidator

# Initialize validator
validator = InputValidator()


web_url = "https://www.pipelagging.com/armaflex-pipe-insulation-lagging-black-nitrile-foam-class-o-2m"
filename = ''.join(web_url.split('.')[1:]).replace('/', '_')
labels_json_path = f"./input_jsons/{filename}"
labels_json_path


# Run validation
result = validator.validate_inputs(
    
    labels_json=labels_json_path,
    url=web_url,
)

# Access results
print(f"Found {len(result.required_components)} components")
print(f"Verified {len([v for v in result.validated_inputs if v.verified])} inputs")
print(f"Missing {len(result.missing_components)} components")