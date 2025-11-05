import { isRemoteUrl } from "./index";

describe("isRemoteUrl", () => {
    describe("Invalid URLs", () => {
        test.each([
            ["", false],
            ["not-a-url", false],
            ["ftp://", false],
            ["http://", false],
            ["https://", false],
            ["//example.com", false],
            ["http://[invalid:ipv6", false],
            ["http://999.999.999.999/", false],
            ["http://256.256.256.256/", false],
            ["http://1.2.3.256/", false],
            ["http://[gggg::1]/", false],
            ["http://[12345::1]/", false],
            ["http://[::ffff:999.999.999.999]/", false],
        ])("should return false for invalid URL: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("File URLs", () => {
        test.each([
            ["file:///home/user/document.txt", false],
            ["file://localhost/c:/windows/file.txt", false],
            ["file:///C:/Users/file.txt", false],
            ["FILE:///home/user/doc.txt", false],
        ])("should return false for file URL: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("Localhost variations", () => {
        test.each([
            ["http://localhost/", false],
            ["http://localhost:8080/", false],
            ["https://localhost/", false],
            ["http://LOCALHOST/", false],
            ["http://LocalHost/", false],
            ["http://localhost.localdomain/", true], // Not just "localhost"
        ])("should handle localhost: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv4 Loopback (127.0.0.0/8)", () => {
        test.each([
            ["http://127.0.0.1/", false],
            ["http://127.0.0.1:8080/", false],
            ["https://127.0.0.1/", false],
            ["http://127.0.0.0/", false],
            ["http://127.0.0.2/", false],
            ["http://127.1.2.3/", false],
            ["http://127.255.255.254/", false],
            ["http://127.255.255.255/", false],
        ])("should return false for loopback: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv4 Private ranges", () => {
        describe("10.0.0.0/8", () => {
            test.each([
                ["http://10.0.0.0/", false],
                ["http://10.0.0.1/", false],
                ["http://10.0.0.1:3000/", false],
                ["http://10.1.2.3/", false],
                ["http://10.255.255.254/", false],
                ["http://10.255.255.255/", false],
            ])("should return false for 10.x.x.x: %s", (url, expected) => {
                expect(isRemoteUrl(url)).toBe(expected);
            });
        });

        describe("172.16.0.0/12", () => {
            test.each([
                ["http://172.16.0.0/", false],
                ["http://172.16.0.1/", false],
                ["http://172.16.255.255/", false],
                ["http://172.20.10.5/", false],
                ["http://172.31.255.254/", false],
                ["http://172.31.255.255/", false],
                // Outside range
                ["http://172.15.255.255/", true],
                ["http://172.32.0.0/", true],
            ])("should handle 172.16-31.x.x: %s", (url, expected) => {
                expect(isRemoteUrl(url)).toBe(expected);
            });
        });

        describe("192.168.0.0/16", () => {
            test.each([
                ["http://192.168.0.0/", false],
                ["http://192.168.0.1/", false],
                ["http://192.168.1.1/", false],
                ["http://192.168.1.254/", false],
                ["http://192.168.255.254/", false],
                ["http://192.168.255.255/", false],
                // Outside range
                ["http://192.167.255.255/", true],
                ["http://192.169.0.0/", true],
            ])("should handle 192.168.x.x: %s", (url, expected) => {
                expect(isRemoteUrl(url)).toBe(expected);
            });
        });
    });

    describe("IPv4 Link-local (169.254.0.0/16)", () => {
        test.each([
            ["http://169.254.0.0/", false],
            ["http://169.254.0.1/", false],
            ["http://169.254.1.1/", false],
            ["http://169.254.255.254/", false],
            ["http://169.254.255.255/", false],
            // Outside range
            ["http://169.253.255.255/", true],
            ["http://169.255.0.0/", true],
        ])("should handle link-local: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv4 Special addresses", () => {
        test.each([
            ["http://0.0.0.0/", false],
            ["http://0.0.0.0:8080/", false],
            ["http://0.0.0.1/", false],
            ["http://0.1.2.3/", false],
            ["http://0.255.255.255/", false],
        ])("should return false for 0.x.x.x: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv4 Public addresses", () => {
        test.each([
            ["http://1.1.1.1/", true],
            ["http://8.8.8.8/", true],
            ["http://8.8.4.4/", true],
            ["https://142.251.41.46/", true],
            ["http://172.217.16.142:443/", true],
            ["http://11.0.0.1/", true],
            ["http://172.15.0.1/", true],
            ["http://172.32.0.1/", true],
            ["http://192.167.1.1/", true],
            ["http://192.169.1.1/", true],
            ["http://169.253.1.1/", true],
            ["http://169.255.1.1/", true],
            ["http://128.0.0.1/", true],
        ])("should return true for public IP: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Loopback", () => {
        test.each([
            ["http://[::1]/", false],
            ["http://[::1]:8080/", false],
            ["http://[0000:0000:0000:0000:0000:0000:0000:0001]/", false],
            ["http://[::0001]/", false],
            ["http://[0:0:0:0:0:0:0:1]/", false],
        ])("should return false for IPv6 loopback: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Unspecified address", () => {
        test.each([
            ["http://[::]/", false],
            ["http://[0000:0000:0000:0000:0000:0000:0000:0000]/", false],
            ["http://[0:0:0:0:0:0:0:0]/", false],
        ])("should return false for unspecified: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Link-local (fe80::/10)", () => {
        test.each([
            ["http://[fe80::]/", false],
            ["http://[fe80::1]/", false],
            ["http://[fe80::1]:8080/", false],
            ["http://[fe80:0000:0000:0000:0204:61ff:fe9d:f156]/", false],
            ["http://[fe80:dead:beef:cafe::]/", false],
            ["http://[febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff]/", false],
            // Zone identifiers (if handled)
            ["http://[fe80::1%eth0]/", false],
            ["http://[fe80::1%25eth0]/", false], // URL encoded %
            // Outside range
            ["http://[fe7f::]/", true],
            ["http://[fec0::]/", true],
        ])("should handle link-local: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Unique local (fc00::/7)", () => {
        test.each([
            ["http://[fc00::]/", false],
            ["http://[fc00::1]/", false],
            ["http://[fc80::1]/", false],
            ["http://[fcff:ffff:ffff:ffff:ffff:ffff:ffff:ffff]/", false],
            ["http://[fd00::]/", false],
            ["http://[fd00::1]/", false],
            ["http://[fd12:3456:789a:bcde::]/", false],
            ["http://[fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff]/", false],
            // Outside range
            ["http://[fbff::]/", true],
            ["http://[fe00::]/", true],
        ])("should handle unique local: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Documentation prefix (2001:db8::/32)", () => {
        test.each([
            ["http://[2001:db8::]/", false],
            ["http://[2001:db8::1]/", false],
            ["http://[2001:db8:85a3::8a2e:370:7334]/", false],
            ["http://[2001:0db8::]/", false],
            // Outside range
            ["http://[2001:db7::]/", true],
            ["http://[2001:db9::]/", true],
        ])("should handle documentation prefix: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 IPv4-mapped addresses (::ffff:0:0/96)", () => {
        test.each([
            // Private IPv4 mapped to IPv6
            ["http://[::ffff:127.0.0.1]/", false],
            ["http://[::ffff:10.0.0.1]/", false],
            ["http://[::ffff:192.168.1.1]/", false],
            ["http://[::ffff:172.16.0.1]/", false],
            ["http://[::ffff:169.254.1.1]/", false],
            ["http://[::ffff:0.0.0.0]/", false],
            // Public IPv4 mapped to IPv6
            ["http://[::ffff:8.8.8.8]/", true],
            ["http://[::ffff:1.1.1.1]/", true],
            ["http://[::ffff:142.251.41.46]/", true],
            // Alternative notation
            ["http://[::ffff:c0a8:0101]/", false], // 192.168.1.1 in hex
        ])("should handle IPv4-mapped: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Public addresses", () => {
        test.each([
            ["http://[2001:4860:4860::8888]/", true], // Google DNS
            ["http://[2001:4860:4860::8844]/", true], // Google DNS
            ["http://[2606:4700:4700::1111]/", true], // Cloudflare
            ["http://[2a00:1450:4001:812::200e]/", true], // Google
            ["http://[2001:470::]/", true],
            ["http://[2001:db7::]/", true], // Just outside documentation range
        ])("should return true for public IPv6: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("IPv6 Abbreviations and formats", () => {
        test.each([
            // Different representations of same address
            ["http://[::1]/", false],
            ["http://[0:0:0:0:0:0:0:1]/", false],
            ["http://[0000:0000:0000:0000:0000:0000:0000:0001]/", false],
            // Leading zeros
            ["http://[fe80:0000:0000:0000:0000:0000:0000:0001]/", false],
            ["http://[fe80:0:0:0:0:0:0:1]/", false],
            ["http://[fe80::0001]/", false],
            // Multiple :: (invalid)
            ["http://[fe80::1::1]/", false],
            // Mixed case
            ["http://[FE80::1]/", false],
            ["http://[Fe80::1]/", false],
            ["http://[fe80::ABC:def]/", false],
        ])("should handle IPv6 format: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe(".local domains (mDNS/Bonjour)", () => {
        test.each([
            ["http://mycomputer.local/", false],
            ["http://mycomputer.local:8080/", false],
            ["https://my-server.local/", false],
            ["http://subdomain.example.local/", false],
            ["http://MYCOMPUTER.LOCAL/", false],
            ["http://MyComputer.Local/", false],
            // Not .local
            ["http://example.localhost/", true],
            ["http://local.example.com/", true],
            ["http://notlocal.com/", true],
        ])("should handle .local domain: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("Regular domain names", () => {
        test.each([
            ["http://example.com/", true],
            ["https://www.example.com/", true],
            ["http://subdomain.example.com/", true],
            ["https://example.co.uk/", true],
            ["http://example.com:8080/", true],
            ["https://api.example.com:443/", true],
            ["http://cdn.cloudflare.com/", true],
            ["https://my-domain.com/", true],
            ["http://xn--e1afmkfd.xn--p1ai/", true], // IDN domain
        ])("should return true for regular domain: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("Edge cases and special scenarios", () => {
        test.each([
            // Protocols
            ["https://192.168.1.1/", false],
            ["http://192.168.1.1/", false],
            ["HTTP://192.168.1.1/", false],
            ["ws://localhost/", false],
            ["wss://localhost/", false],

            // Ports
            ["http://localhost:80/", false],
            ["http://localhost:443/", false],
            ["http://localhost:3000/", false],
            ["http://localhost:65535/", false],
            ["http://192.168.1.1:8080/", false],
            ["http://[::1]:8080/", false],

            // Paths and query strings
            ["http://localhost/path/to/resource", false],
            ["http://localhost/?query=param", false],
            ["http://localhost/#hash", false],
            ["http://192.168.1.1/api/endpoint?key=value#section", false],

            // Username/password in URL
            ["http://user:pass@localhost/", false],
            ["http://user:pass@192.168.1.1/", false],
            ["http://user:pass@example.com/", true],

            // Mixed scenarios
            ["http://localhost.example.com/", true], // Not just localhost
            ["http://127.0.0.1.example.com/", true], // Not an IP
            ["http://192-168-1-1.example.com/", true], // Domain, not IP
        ])("should handle edge case: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("Invalid but parseable URLs", () => {
        test.each([
            ["http://[::ffff:300.300.300.300]/", false], // Invalid IPv4 in IPv6
            ["http://[fffff::]/", false], // Invalid hex group
            ["http://[12345678::]/", false], // Too many digits
            ["http://[::1::2]/", false], // Multiple ::
            ["http://[1:2:3:4:5:6:7:8:9]/", false], // Too many groups
        ])("should handle invalid but parseable: %s", (url, expected) => {
            expect(isRemoteUrl(url)).toBe(expected);
        });
    });

    describe("Performance and stress tests", () => {
        test("should handle very long domain names", () => {
            const longDomain = "a".repeat(63) + ".com";
            expect(isRemoteUrl(`http://${longDomain}/`)).toBe(true);
        });

        test("should handle maximum length IPv6", () => {
            const maxIPv6 = "http://[ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff]/";
            expect(isRemoteUrl(maxIPv6)).toBe(true);
        });

        test("should handle URLs with many subdomains", () => {
            const manySubdomains = "a.b.c.d.e.f.g.h.example.com";
            expect(isRemoteUrl(`http://${manySubdomains}/`)).toBe(true);
        });
    });
});
