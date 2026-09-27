pkgname=pipesync
pkgver=1.0.0
pkgrel=1
pkgdesc="Ultra-Low-Latency Multi-Device Audio Sharing & Synchronization for PipeWire"
arch=('any')
url="https://github.com/MayurUbarhande0/pipesync"
license=('MIT')

depends=(
    python
    python-gobject
    gtk4
    libadwaita
)

makedepends=(
    python-build
    python-installer
    python-setuptools
)

source=()
sha256sums=()

build() {
    python -m build --wheel --no-isolation
}

package() {
    python -m installer --destdir="$pkgdir" dist/*.whl
}