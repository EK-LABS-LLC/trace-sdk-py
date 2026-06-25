.PHONY: bump

bump:
	@test -n "$(VERSION)" || (echo "Usage: make bump VERSION=x.y.z"; exit 2)
	./scripts/bump-version.sh "$(VERSION)"
