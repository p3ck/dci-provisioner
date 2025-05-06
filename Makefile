.PHONY: build-dci-provisioner-image
build-dci-provisioner-image:
	podman build --file Containerfiles/Containerfile-provisioner --tag quay.io/p3ck/dci-provisioner:latest .

.PHONY: build-dci-lab-image
build-dci-lab-image:
	podman build --file Containerfiles/Containerfile-lab --tag quay.io/p3ck/dci-lab:latest .

.PHONY: build-podman-images
build-podman-images: build-dci-provisioner-image build-dci-lab-image

.PHONY: release-podman-images
release-podman-images: build-podman-images
	podman push quay.io/p3ck/dci-provisioner:latest
	podman push quay.io/p3ck/dci-lab:latest
