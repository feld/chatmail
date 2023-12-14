import requests
from ipaddress import ip_address
from json.decoder import JSONDecodeError

resolvers = [
    "https://dns.nextdns.io/dns-query",
    "https://dns.google/resolve",
    "https://cloudflare-dns.com/dns-query",
]
dns_types = {
    "A": 1,
    "AAAA": 28,
    "CNAME": 5,
    "MX": 15,
    "SRV": 33,
    "CAA": 257,
    "TXT": 16,
    "PTR": 12,
}


class DNS:
    def __init__(self, out, ssh):
        self.session = requests.Session()
        self.out = out
        self.ssh = ssh

    def get_ipv4(self):
        cmd = "ip a | grep 'inet ' | grep 'scope global' | grep -oE '[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}' | head -1"
        return self.out.shell_output(f"{self.ssh} -- {cmd}").strip()

    def get_ipv6(self):
        cmd = "ip a | grep inet6 | grep 'scope global' | sed -e 's#/64 scope global##' | sed -e 's#inet6##'"
        return self.out.shell_output(f"{self.ssh} -- {cmd}").strip()

    def get(self, typ: str, domain: str) -> str:
        """Get a DNS entry"""
        for url in resolvers:
            r = self.session.get(
                url,
                params={"name": domain, "type": typ},
                headers={"accept": "application/dns-json"},
            )

            try:
                j = r.json()
            except JSONDecodeError:
                # ignore DNS resolvers which don't give us JSON
                continue
            if "Answer" in j:
                for answer in j["Answer"]:
                    if answer["type"] == dns_types[typ]:
                        return answer["data"]
        return ""

    def resolve_mx(self, domain: str) -> (str, str):
        """Resolve an MX entry"""
        for url in resolvers:
            r = self.session.get(
                url,
                params={"name": domain, "type": "MX"},
                headers={"accept": "application/dns-json"},
            )

            try:
                j = r.json()
            except JSONDecodeError:
                # ignore DNS resolvers which don't give us JSON
                continue
            if "Answer" in j:
                result = (0, None)
                for answer in j["Answer"]:
                    if answer["type"] == dns_types["MX"]:
                        prio, server_name = answer["data"].split()
                        if int(prio) > result[0]:
                            result = (int(prio), server_name)
                return result
        return None, None

    def resolve(self, domain: str) -> str:
        result = self.get("A", domain)
        if not result:
            result = self.get("CNAME", domain)
            if result:
                result = self.get("A", result[:-1])
                if not result:
                    result = self.get("AAAA", domain)
        return result

    def check_ptr_record(self, ip: str, mail_domain) -> str:
        """Check the PTR record for an IPv4 or IPv6 address."""
        result = self.get("PTR", ip_address(ip).reverse_pointer)
        return result[:-1] == mail_domain
