.PHONY: v1tov2
v1tov2:
	python -m scripts.v1tov2 data/v1/medline/phase3-review/ data/v2/medline/ehealth2019
	python -m scripts.v1tov2 data/v1/medline/trial.txt data/v2/medline/ehealth2019/trial.txt

.PHONY: clean
clean:
	git clean -fxd