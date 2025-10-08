Priority 1: OCR Steps (HIGHEST)
  ↓ Why first? OCR usage overrides cache - if OCR ran, cache can't be used
  
Priority 2: Unblocker Call
  ↓ Why second? Blocker steps are special retry mechanisms, different flow
  
Priority 3: Failed Step
  ↓ Why third? If step failed, that's the primary issue to report
  
Priority 4: Cache Read Status None (Dynamic Components)
  ↓ Why fourth? No cache attempt = different scenario than cache failure
  
Priority 5: Cache Miss (cache_read_status = -1)
  ↓ Why fifth? Cache was tried but found nothing
  
Priority 6: Failed At Must Match Filter
  ↓ Why sixth? Found similar doc but failed at component matching
  
Priority 7: Failed After Similar Document
  ↓ Why seventh? Found similar doc, passed must_match, but failed later filters
  
Priority 8: Unclassified (LOWEST)
  ↓ Catch-all for anything that doesn't fit above
