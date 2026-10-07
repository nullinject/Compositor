import Testing
@testable import Compositor

struct CompatibilityBudgetTests {
    @Test func eightGiBMacKeepsEachRasterCacheWithin256MiB() {
        let memory: UInt64 = 8 * 1024 * 1024 * 1024
        let pixels = DocumentLimits.rasterCachePixelBudget(maximum: 200_000_000, physicalMemory: memory)
        #expect(pixels == 67_108_864)
        #expect(pixels * 4 == 256 * 1024 * 1024)
    }

    @Test func largerMacsNeverExceedExistingCacheCeilings() {
        let memory: UInt64 = 64 * 1024 * 1024 * 1024
        #expect(DocumentLimits.rasterCachePixelBudget(maximum: 200_000_000, physicalMemory: memory) == 200_000_000)
        #expect(DocumentLimits.rasterCachePixelBudget(maximum: 150_000_000, physicalMemory: memory) == 150_000_000)
    }

    @Test func cacheBudgetStaysPositiveIfMemoryIsUnknown() {
        #expect(DocumentLimits.rasterCachePixelBudget(maximum: 200_000_000, physicalMemory: 0) == 1)
    }
}
