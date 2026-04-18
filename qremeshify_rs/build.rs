fn main() {
    // Tell PyO3 to configure the build for the Python interpreter
    // This resolves the Python version and sets appropriate linker flags
    pyo3_build_config::use_pyo3_cfgs();
}
