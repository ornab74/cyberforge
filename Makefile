.PHONY: setup run verify flutter
setup:
	./tool/setup_sidecar.sh
run:
	./tool/run_dev.sh
verify:
	./tool/verify.sh
flutter:
	flutter pub get && flutter run -d linux
